"""
Cliente async para WebDAV (TorBox).
Maneja conexiones y caché de directorios.
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

@dataclass
class VFSFile:
    """Representa un archivo en el VFS"""
    name: str
    size: int
    is_dir: bool
    mtime: datetime
    path: str = ""
    
    def to_dict(self):
        return {
            'name': self.name,
            'size': self.size,
            'is_dir': self.is_dir,
            'mtime': self.mtime.timestamp(),
            'path': self.path
        }

@dataclass
class DirCache:
    """Cache de directorios con TTL"""
    files: List[VFSFile]
    timestamp: datetime
    ttl_seconds: int = 30
    
    def is_expired(self) -> bool:
        return datetime.now() - self.timestamp > timedelta(seconds=self.ttl_seconds)

class TorBoxWebDAVClient:
    """Cliente async para WebDAV de TorBox"""
    
    def __init__(self, torbox_url: str, torbox_user: str, torbox_pass: str):
        self.torbox_url = torbox_url.rstrip('/')
        self.torbox_user = torbox_user
        self.torbox_pass = torbox_pass
        self.dir_cache: Dict[str, DirCache] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.lock = asyncio.Lock()
        
    async def __aenter__(self):
        auth = aiohttp.BasicAuth(self.torbox_user, self.torbox_pass)
        self.session = aiohttp.ClientSession(auth=auth)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def connect(self):
        """Conectar al servidor WebDAV"""
        if not self.session:
            auth = aiohttp.BasicAuth(self.torbox_user, self.torbox_pass)
            self.session = aiohttp.ClientSession(auth=auth)
    
    async def disconnect(self):
        """Desconectar"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def list_dir(self, path: str = "/") -> List[VFSFile]:
        """
        Lista archivos en un directorio.
        Usa caché con TTL de 30 segundos.
        """
        path = path.rstrip('/') or '/'
        
        # Verificar caché
        if path in self.dir_cache and not self.dir_cache[path].is_expired():
            logger.debug(f"[VFSClient] Cache hit for {path}")
            return self.dir_cache[path].files
        
        logger.debug(f"[VFSClient] Fetching {path} from WebDAV")
        
        if not self.session:
            await self.connect()
        
        try:
            url = self.torbox_url + path
            
            # PROPFIND para listar
            async with self.session.request('PROPFIND', url, headers={'Depth': '1'}) as resp:
                if resp.status not in [207, 200]:
                    logger.error(f"[VFSClient] Error listing {path}: {resp.status}")
                    return []
                
                # Parse XML response
                text = await resp.text()
                files = self._parse_propfind(text, path)
                
                # Cachear
                self.dir_cache[path] = DirCache(files=files, timestamp=datetime.now())
                return files
                
        except Exception as e:
            logger.error(f"[VFSClient] Error listing {path}: {e}")
            return []
    
    async def get_file_info(self, path: str) -> Optional[VFSFile]:
        """Obtiene info de un archivo específico"""
        if not self.session:
            await self.connect()
        
        try:
            url = self.torbox_url + path
            async with self.session.request('PROPFIND', url, headers={'Depth': '0'}) as resp:
                if resp.status not in [207, 200]:
                    return None
                
                text = await resp.text()
                files = self._parse_propfind(text, path)
                return files[0] if files else None
                
        except Exception as e:
            logger.error(f"[VFSClient] Error getting info for {path}: {e}")
            return None
    
    async def read_file(self, path: str, offset: int = 0, size: int = None) -> bytes:
        """Lee contenido de un archivo"""
        if not self.session:
            await self.connect()
        
        try:
            url = self.torbox_url + path
            headers = {}
            
            if size:
                headers['Range'] = f'bytes={offset}-{offset + size - 1}'
            elif offset:
                headers['Range'] = f'bytes={offset}-'
            
            async with self.session.get(url, headers=headers) as resp:
                if resp.status not in [200, 206]:
                    logger.error(f"[VFSClient] Error reading {path}: {resp.status}")
                    return b''
                
                return await resp.read()
                
        except Exception as e:
            logger.error(f"[VFSClient] Error reading {path}: {e}")
            return b''
    
    def invalidate_cache(self, path: str = None):
        """Invalida caché de directorios"""
        if path:
            self.dir_cache.pop(path, None)
            logger.debug(f"[VFSClient] Cache invalidated for {path}")
        else:
            self.dir_cache.clear()
            logger.debug(f"[VFSClient] All cache invalidated")
    
    def _parse_propfind(self, xml: str, base_path: str) -> List[VFSFile]:
        """Parsea respuesta PROPFIND (simple XML parsing)"""
        files = []
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(xml)
            
            # Namespaces típicos de WebDAV
            namespaces = {
                'd': 'DAV:',
                'o': 'http://apache.org/dav/props/'
            }
            
            for response in root.findall('.//d:response', namespaces):
                href_elem = response.find('d:href', namespaces)
                if href_elem is None:
                    continue
                
                href = href_elem.text
                if not href or href == base_path or href == base_path.rstrip('/') + '/':
                    continue  # Skip self
                
                # Extraer nombre
                name = href.rstrip('/').split('/')[-1]
                
                # Obtener propiedades
                props = response.find('.//d:prop', namespaces)
                if props is None:
                    continue
                
                # Detectar si es directorio
                is_dir = props.find('d:resourcetype/d:collection', namespaces) is not None
                
                # Tamaño
                size_elem = props.find('d:getcontentlength', namespaces)
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0
                
                # Fecha modificación
                mtime_elem = props.find('d:getlastmodified', namespaces)
                mtime = datetime.now()
                if mtime_elem is not None and mtime_elem.text:
                    try:
                        # RFC 2822 format
                        from email.utils import parsedate_to_datetime
                        mtime = parsedate_to_datetime(mtime_elem.text)
                    except:
                        pass
                
                files.append(VFSFile(
                    name=name,
                    size=size,
                    is_dir=is_dir,
                    mtime=mtime,
                    path=href
                ))
        
        except Exception as e:
            logger.error(f"[VFSClient] Error parsing PROPFIND: {e}")
        
        return files
