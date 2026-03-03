"""
Cliente sincrónico para WebDAV (TorBox).
Usa `requests` en lugar de `aiohttp` para ser compatible con threads de trio/pyfuse3.
"""
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

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
    """Cliente sincrónico para WebDAV de TorBox (basado en requests)."""

    def __init__(self, torbox_url: str, torbox_user: str, torbox_pass: str):
        self.torbox_url = torbox_url.rstrip('/')
        self.torbox_user = torbox_user
        self.torbox_pass = torbox_pass
        self.dir_cache: Dict[str, DirCache] = {}
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = (self.torbox_user, self.torbox_pass)
        return self._session

    def connect(self):
        """Inicializa la sesión HTTP."""
        _ = self.session  # Trigger lazy init

    def disconnect(self):
        """Cierra la sesión HTTP."""
        if self._session:
            self._session.close()
            self._session = None

    def list_dir(self, path: str = "/") -> List[VFSFile]:
        """Lista archivos en un directorio con caché TTL de 30s."""
        path = path.rstrip('/') or '/'

        if path in self.dir_cache and not self.dir_cache[path].is_expired():
            logger.debug(f"[VFSClient] Cache hit for {path}")
            return self.dir_cache[path].files

        logger.debug(f"[VFSClient] Fetching {path} from WebDAV")

        for attempt in range(3):  # Retry hasta 3 veces
            try:
                url = self.torbox_url + path
                resp = self.session.request('PROPFIND', url, headers={'Depth': '1'}, timeout=15)
                if resp.status_code not in [207, 200]:
                    logger.error(f"[VFSClient] Error listing {path}: HTTP {resp.status_code}")
                    if attempt < 2:
                        continue
                    return []

                files = self._parse_propfind(resp.text, path)
                self.dir_cache[path] = DirCache(files=files, timestamp=datetime.now())
                return files

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[VFSClient] Connection error (attempt {attempt+1}/3): {e}")
                # Resetear la sesión para reconectar
                self._session = None
                if attempt == 2:
                    return []
            except Exception as e:
                logger.error(f"[VFSClient] Error listing {path}: {e}")
                return []

        return []

    def get_file_info(self, path: str) -> Optional[VFSFile]:
        """Obtiene info de un archivo específico."""
        try:
            url = self.torbox_url + path
            resp = self.session.request('PROPFIND', url, headers={'Depth': '0'}, timeout=10)
            if resp.status_code not in [207, 200]:
                return None

            files = self._parse_propfind(resp.text, path)
            return files[0] if files else None

        except Exception as e:
            logger.error(f"[VFSClient] Error getting info for {path}: {e}")
            return None

    def read_file(self, path: str, offset: int = 0, size: int = None) -> bytes:
        """Lee contenido de un archivo."""
        try:
            url = self.torbox_url + path
            headers = {}
            if size:
                headers['Range'] = f'bytes={offset}-{offset + size - 1}'
            elif offset:
                headers['Range'] = f'bytes={offset}-'

            resp = self.session.get(url, headers=headers, timeout=30)
            if resp.status_code not in [200, 206]:
                logger.error(f"[VFSClient] Error reading {path}: {resp.status_code}")
                return b''
            return resp.content

        except Exception as e:
            logger.error(f"[VFSClient] Error reading {path}: {e}")
            return b''

    def invalidate_cache(self, path: str = None):
        if path:
            self.dir_cache.pop(path, None)
        else:
            self.dir_cache.clear()

    def _normalize_href(self, href: str) -> str:
        """Extrae solo el path de un href WebDAV (que puede ser URL completa o path)."""
        from urllib.parse import urlparse, unquote
        parsed = urlparse(href)
        if parsed.scheme:
            # Es una URL completa, extraer solo el path
            return parsed.path
        return href

    def _parse_propfind(self, xml: str, base_path: str) -> List[VFSFile]:
        files = []
        try:
            import xml.etree.ElementTree as ET
            from urllib.parse import unquote

            root = ET.fromstring(xml)
            namespaces = {'d': 'DAV:'}

            # Intentar también namespace sin prefijo
            for response in root.iter():
                if not response.tag.endswith('}response') and response.tag != 'response':
                    continue

                ns = ''
                if '}' in response.tag:
                    ns = response.tag.split('}')[0] + '}'

                href_elem = response.find(f'{ns}href')
                if href_elem is None:
                    continue

                href = self._normalize_href(href_elem.text or '')

                # Saltar el directorio base mismo
                base_normalized = base_path.rstrip('/')
                href_normalized = href.rstrip('/')
                if href_normalized == base_normalized or href_normalized == '':
                    continue

                name = unquote(href_normalized.split('/')[-1])
                if not name:
                    continue

                props = response.find(f'{ns}propstat/{ns}prop') or response.find(f'{ns}prop')
                if props is None:
                    continue

                is_dir = props.find(f'{ns}resourcetype/{ns}collection') is not None

                size_elem = props.find(f'{ns}getcontentlength')
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

                mtime_elem = props.find(f'{ns}getlastmodified')
                mtime = datetime.now()
                if mtime_elem is not None and mtime_elem.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        mtime = parsedate_to_datetime(mtime_elem.text)
                    except Exception:
                        pass

                # Guardar el path normalizado (URL-decoded para uso interno)
                stored_path = href_normalized

                files.append(VFSFile(
                    name=name,
                    size=size,
                    is_dir=is_dir,
                    mtime=mtime,
                    path=stored_path
                ))

        except Exception as e:
            logger.error(f"[VFSClient] Error parsing PROPFIND: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return files
