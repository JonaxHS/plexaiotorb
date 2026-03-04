"""
FUSE Virtual Filesystem for TorBox
Exposes TorBox files as a structured Plex-compatible directory tree
with intelligent caching and lazy loading.
"""

import os
import sys
import time
import logging
import threading
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import errno
from collections import OrderedDict

try:
    from fuse import FUSE, FuseOSError, Operations
except ImportError:
    print("ERROR: fusepy no instalado. Instala con: pip install fusepy")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TorBoxVFS] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class CacheManager:
    """Gestiona cache LRU con límite de 100GB"""
    
    def __init__(self, cache_dir: str, max_size_mb: int = 100 * 1024):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        self.files: Dict[str, Tuple[Path, float]] = {}  # {cache_key: (path, last_access)}
        self.lock = threading.Lock()
        self._load_cache_state()
    
    def _load_cache_state(self):
        """Cargar estado de caché existente"""
        for cache_file in self.cache_dir.glob("**/*"):
            if cache_file.is_file():
                cache_key = str(cache_file.relative_to(self.cache_dir))
                self.files[cache_key] = (cache_file, time.time())
    
    def _get_cache_size_mb(self) -> int:
        """Obtener tamaño total del caché en MB"""
        total_bytes = sum(
            f.stat().st_size for f in self.cache_dir.rglob("*") if f.is_file()
        )
        return total_bytes // (1024 * 1024)
    
    def _evict_lru(self, needed_mb: int):
        """Eliminar archivos menos recientemente usados para liberar espacio"""
        with self.lock:
            # Ordenar por último acceso (menos reciente primero)
            sorted_files = sorted(
                self.files.items(), 
                key=lambda x: x[1][1]
            )
            
            freed_mb = 0
            for cache_key, (path, _) in sorted_files:
                if freed_mb >= needed_mb:
                    break
                
                try:
                    size_mb = path.stat().st_size // (1024 * 1024)
                    if path.exists():
                        path.unlink()
                        logger.info(f"[Cache] Evicted {cache_key} ({size_mb}MB)")
                    del self.files[cache_key]
                    freed_mb += size_mb
                except Exception as e:
                    logger.error(f"[Cache] Error evicting {cache_key}: {e}")
    
    def get(self, cache_key: str) -> Optional[Path]:
        """Obtener archivo del caché (actualiza last_access)"""
        with self.lock:
            if cache_key in self.files:
                path, _ = self.files[cache_key]
                self.files[cache_key] = (path, time.time())
                return path if path.exists() else None
        return None
    
    def put(self, cache_key: str, source_path: str) -> Path:
        """Copiar archivo al caché"""
        with self.lock:
            cache_path = self.cache_dir / cache_key
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check size y evict si necesario
            current_size_mb = self._get_cache_size_mb()
            source_size_mb = os.path.getsize(source_path) // (1024 * 1024)
            
            if current_size_mb + source_size_mb > self.max_size_mb:
                needed = current_size_mb + source_size_mb - self.max_size_mb
                logger.info(f"[Cache] Need {needed}MB, evicting LRU files...")
                self._evict_lru(needed + 100)  # +100MB buffer
            
            # Copiar archivo
            logger.info(f"[Cache] Cacheing {cache_key} ({source_size_mb}MB)")
            shutil.copy2(source_path, cache_path)
            
            self.files[cache_key] = (cache_path, time.time())
            return cache_path
    
    def get_stats(self) -> Dict:
        """Obtener estado del caché"""
        return {
            "total_files": len(self.files),
            "cache_size_mb": self._get_cache_size_mb(),
            "max_size_mb": self.max_size_mb,
            "cache_dir": str(self.cache_dir)
        }


class TorBoxVFS(Operations):
    """FUSE Operations para TorBox VFS"""
    
    def __init__(self, torbox_mount: str, cache_dir: str, vfs_mount: str):
        self.torbox_mount = Path(torbox_mount)
        self.vfs_mount = Path(vfs_mount)
        self.cache = CacheManager(cache_dir, max_size_mb=100 * 1024)
        self.file_struct: Dict[str, Dict] = {}  # Estructura virtual de directorios
        self.lock = threading.Lock()
        self._update_file_structure()
        
        # Thread para monitorear TorBox cada 60s
        self.monitor_thread = threading.Thread(
            target=self._monitor_torbox, daemon=True
        )
        self.monitor_thread.start()
    
    def _monitor_torbox(self):
        """Monitorear TorBox cada 60 segundos para nuevos archivos"""
        while True:
            try:
                time.sleep(60)
                logger.info("[Monitor] Checking TorBox for new files...")
                self._update_file_structure()
            except Exception as e:
                logger.error(f"[Monitor] Error: {e}")
    
    def _update_file_structure(self):
        """Actualizar estructura de archivos desde TorBox"""
        try:
            entries = os.listdir(self.torbox_mount)
            new_struct = {
                "Movies": {},
                "Shows": {}
            }
            
            for entry in entries:
                try:
                    source_path = self.torbox_mount / entry
                    
                    # Determinar si es película o serie per metadata
                    # Por ahora: películas si tiene año, series si tiene S##E##
                    if "s" in entry.lower() and "e" in entry.lower():
                        # Es serie
                        show_name = entry.split(".S")[0].replace(".", " ").strip()
                        if show_name not in new_struct["Shows"]:
                            new_struct["Shows"][show_name] = []
                        new_struct["Shows"][show_name].append(entry)
                    else:
                        # Es película
                        movie_name = entry.replace(".", " ").strip()
                        new_struct["Movies"][movie_name] = entry
                except Exception as e:
                    logger.warning(f"[Monitor] Error processing {entry}: {e}")
            
            with self.lock:
                self.file_struct = new_struct
                logger.info(f"[Monitor] Updated: {len(new_struct['Movies'])} movies, {len(new_struct['Shows'])} shows")
        
        except Exception as e:
            logger.error(f"[Monitor] Error updating structure: {e}")
    
    def getattr(self, path, fh=None):
        """Get file attributes"""
        logger.debug(f"getattr: {path}")
        
        parts = path.strip("/").split("/")
        
        if path == "/":
            st = os.stat(self.torbox_mount)
            return dict(
                st_mode=st.st_mode,
                st_nlink=1,
                st_uid=os.getuid(),
                st_gid=os.getgid(),
                st_rdev=0,
                st_size=4096,
                st_blksize=512,
                st_blocks=8,
                st_atime=st.st_atime,
                st_mtime=st.st_mtime,
                st_ctime=st.st_ctime
            )
        
        # Navegar estructura
        with self.lock:
            if parts[0] not in ["Movies", "Shows"]:
                raise FuseOSError(errno.ENOENT)
            
            current = self.file_struct.get(parts[0], {})
            
            for i, part in enumerate(parts[1:], 1):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, str):
                    # Es archivo final
                    source_path = self.torbox_mount / current
                    try:
                        st = os.stat(source_path)
                        return dict(
                            st_mode=0o100644,  # Regular file
                            st_nlink=1,
                            st_uid=os.getuid(),
                            st_gid=os.getgid(),
                            st_rdev=0,
                            st_size=st.st_size,
                            st_blksize=512,
                            st_blocks=(st.st_size + 511) // 512,
                            st_atime=st.st_atime,
                            st_mtime=st.st_mtime,
                            st_ctime=st.st_ctime
                        )
                    except:
                        raise FuseOSError(errno.ENOENT)
                else:
                    raise FuseOSError(errno.ENOENT)
            
            # Es directorio
            return dict(
                st_mode=0o040755,  # Directory
                st_nlink=2,
                st_uid=os.getuid(),
                st_gid=os.getgid(),
                st_rdev=0,
                st_size=4096,
                st_blksize=512,
                st_blocks=8,
                st_atime=time.time(),
                st_mtime=time.time(),
                st_ctime=time.time()
            )
    
    def readdir(self, path, fh):
        """List directory contents"""
        logger.debug(f"readdir: {path}")
        
        parts = path.strip("/").split("/")
        
        with self.lock:
            if path == "/":
                return [".", "..", "Movies", "Shows"]
            
            current = self.file_struct.get(parts[0], {})
            for part in parts[1:]:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    raise FuseOSError(errno.ENOENT)
            
            if isinstance(current, dict):
                return [".", ".."] + list(current.keys())
            else:
                raise FuseOSError(errno.ENOTDIR)
    
    def open(self, path, flags):
        """Open file"""
        logger.info(f"open: {path}")
        return 0
    
    def read(self, path, length, offset, fh):
        """Read file contents (con caching)"""
        logger.info(f"read: {path} (offset={offset}, length={length})")
        
        parts = path.strip("/").split("/")
        
        with self.lock:
            current = self.file_struct.get(parts[0], {})
            for part in parts[1:]:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    raise FuseOSError(errno.ENOENT)
            
            if isinstance(current, str):
                source_path = self.torbox_mount / current
                
                # Generar cache key
                cache_key = f"{parts[0]}/{current}"
                
                # Verificar si está en caché
                cached_path = self.cache.get(cache_key)
                if not cached_path:
                    # Copiar a caché
                    cached_path = self.cache.put(cache_key, str(source_path))
                
                # Leer del caché
                with open(cached_path, "rb") as f:
                    f.seek(offset)
                    return f.read(length)
        
        raise FuseOSError(errno.ENOENT)
    
    def release(self, path, fh):
        """Close file"""
        return 0


def main(torbox_mount: str, vfs_mount: str, cache_dir: str):
    """Iniciar FUSE VFS"""
    logger.info(f"Starting TorBox VFS")
    logger.info(f"  TorBox mount: {torbox_mount}")
    logger.info(f"  VFS mount: {vfs_mount}")
    logger.info(f"  Cache dir: {cache_dir}")
    
    Path(vfs_mount).mkdir(parents=True, exist_ok=True)
    
    fuse = FUSE(
        TorBoxVFS(torbox_mount, cache_dir, vfs_mount),
        vfs_mount,
        foreground=True,
        allow_other=True,
        nonempty=True
    )


if __name__ == "__main__":
    main(
        torbox_mount="/mnt/torbox",
        vfs_mount="/mnt/torbox_vfs",
        cache_dir="/tmp/torbox_cache"
    )
