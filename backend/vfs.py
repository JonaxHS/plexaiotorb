"""
VFS Custom basado en pyfuse3.
Filesystem virtual con control total y sin rate limiting.
"""
import pyfuse3
import logging
from typing import Dict, Optional, Tuple
from pathlib import PurePosixPath
import errno
from stat import S_IFREG, S_IFDIR, S_IFLNK
import asyncio
from vfs_client import TorBoxWebDAVClient, VFSFile

logger = logging.getLogger(__name__)

class TorBoxVFS(pyfuse3.Operations):
    """VFS para montar TorBox via pyfuse3"""
    
    def __init__(self, torbox_url: str, torbox_user: str, torbox_pass: str):
        super().__init__()
        self.client = TorBoxWebDAVClient(torbox_url, torbox_user, torbox_pass)
        self._inode_map: Dict[int, str] = {pyfuse3.ROOT_INODE: "/"}
        self._path_to_inode: Dict[str, int] = {"/": pyfuse3.ROOT_INODE}
        self._next_inode = pyfuse3.ROOT_INODE + 1
        self._attr_cache: Dict[int, pyfuse3.EntryAttributes] = {}
        self.loop = asyncio.get_event_loop()
    
    async def startup(self):
        """Inicializa el cliente WebDAV"""
        logger.info("[VFS] Starting TorBox VFS")
        await self.client.connect()
    
    async def shutdown(self):
        """Cierra conexiones"""
        logger.info("[VFS] Shutting down TorBox VFS")
        await self.client.disconnect()
    
    def _get_inode(self, path: str) -> int:
        """Obtiene o crea inode para una ruta"""
        path = path.rstrip('/') or '/'
        
        if path in self._path_to_inode:
            return self._path_to_inode[path]
        
        inode = self._next_inode
        self._next_inode += 1
        self._inode_map[inode] = path
        self._path_to_inode[path] = inode
        
        return inode
    
    def _get_path(self, inode: int) -> str:
        """Obtiene ruta desde inode"""
        return self._inode_map.get(inode, "/")
    
    async def lookup(self, parent_inode, name, ctx=None):
        """Resolve filename to inode"""
        parent_path = self._get_path(parent_inode)
        name_str = name.decode() if isinstance(name, bytes) else name
        
        # Construir ruta
        if parent_path == "/":
            path = f"/{name_str}"
        else:
            path = f"{parent_path}/{name_str}"
        
        logger.debug(f"[VFS] lookup: {path}")
        
        try:
            file_info = await self.client.get_file_info(path)
            if not file_info:
                raise pyfuse3.FUSEError(errno.ENOENT)
            
            return self._make_entry_attr(file_info)
        except Exception as e:
            logger.error(f"[VFS] lookup error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.ENOENT)
    
    async def readdir(self, inode, offset, ctx=None):
        """List directory"""
        path = self._get_path(inode)
        logger.debug(f"[VFS] readdir: {path}")
        
        try:
            files = await self.client.list_dir(path)
            
            # Entrys predefinidos
            entries = []
            if offset == 0:
                # . y ..
                entries.append((b'.', self._make_entry_attr_simple('.', True), 1))
                entries.append((b'..', self._make_entry_attr_simple('..', True), 2))
            
            # Archivos
            for i, file_info in enumerate(files, start=3):
                file_inode = self._get_inode(file_info.path.rstrip('/') if not file_info.is_dir else file_info.path)
                attr = self._make_entry_attr(file_info)
                entries.append((file_info.name.encode(), attr, i + offset))
            
            for name, attr, off in entries[offset:]:
                yield (name, attr, off)
                
        except Exception as e:
            logger.error(f"[VFS] readdir error for {path}: {e}")
    
    async def getattr(self, inode, ctx=None):
        """Get file attributes"""
        path = self._get_path(inode)
        logger.debug(f"[VFS] getattr: {path}")
        
        try:
            if inode == pyfuse3.ROOT_INODE:
                return self._make_attr(inode, True, 0)
            
            file_info = await self.client.get_file_info(path)
            if not file_info:
                raise pyfuse3.FUSEError(errno.ENOENT)
            
            return self._make_attr(inode, file_info.is_dir, file_info.size, file_info.mtime.timestamp())
            
        except Exception as e:
            logger.error(f"[VFS] getattr error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.ENOENT)
    
    async def open(self, inode, flags, ctx=None):
        """Open file"""
        path = self._get_path(inode)
        logger.debug(f"[VFS] open: {path}")
        
        return pyfuse3.FileInfo(fh=inode)
    
    async def read(self, fh, offset, size):
        """Read file content"""
        inode = fh
        path = self._get_path(inode)
        logger.debug(f"[VFS] read: {path} offset={offset} size={size}")
        
        try:
            data = await self.client.read_file(path, offset, size)
            return data
        except Exception as e:
            logger.error(f"[VFS] read error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.EIO)
    
    def _make_attr(self, inode: int, is_dir: bool, size: int = 0, mtime: float = None) -> pyfuse3.EntryAttributes:
        """Crea atributos FUSE"""
        from time import time
        timestamp = mtime if mtime else time()
        
        attr = pyfuse3.EntryAttributes()
        attr.st_ino = inode
        attr.st_mode = (S_IFDIR | 0o755) if is_dir else (S_IFREG | 0o644)
        attr.st_nlink = 2 if is_dir else 1
        attr.st_uid = 0
        attr.st_gid = 0
        attr.st_rdev = 0
        attr.st_size = size
        attr.st_blksize = 4096
        attr.st_blocks = (size + 511) // 512
        ts_ns = int(timestamp * 1e9)

        # Compatibilidad entre builds de pyfuse3 (algunas exponen *_ns, otras también st_atime/st_mtime/st_ctime)
        for field_name, field_value in (
            ("st_atime", int(timestamp)),
            ("st_mtime", int(timestamp)),
            ("st_ctime", int(timestamp)),
            ("st_atime_ns", ts_ns),
            ("st_mtime_ns", ts_ns),
            ("st_ctime_ns", ts_ns),
        ):
            try:
                setattr(attr, field_name, field_value)
            except Exception:
                pass
        attr.generation = 0
        
        attr.entry_timeout = 60    # TTL entries
        attr.attr_timeout = 60     # TTL attributes
        
        return attr
    
    def _make_entry_attr(self, file_info: VFSFile) -> pyfuse3.EntryAttributes:
        """Crea EntryAttributes desde VFSFile"""
        inode = self._get_inode(file_info.path.rstrip('/') if not file_info.is_dir else file_info.path)
        return self._make_attr(inode, file_info.is_dir, file_info.size, file_info.mtime.timestamp())
    
    def _make_entry_attr_simple(self, name: str, is_dir: bool) -> pyfuse3.EntryAttributes:
        """Crea EntryAttributes simple"""
        inode = hash(name) % (2**31 - 1) + 1
        return self._make_attr(inode, is_dir, 0)

async def mount_torbox_vfs(torbox_url: str, torbox_user: str, torbox_pass: str, mount_point: str):
    """Monta el VFS de TorBox usando un hilo separado para no bloquear FastAPI."""
    logger.info(f"[VFS] Mounting TorBox at {mount_point}")
    
    vfs = TorBoxVFS(torbox_url, torbox_user, torbox_pass)
    
    try:
        await vfs.startup()
        
        # Opciones FUSE mínimas y compatibles (sin nonempty que no está disponible en FUSE3)
        fuse_options = set(pyfuse3.default_options)
        fuse_options.add("fsname=torbox_vfs")
        fuse_options.add("allow_other")

        pyfuse3.init(vfs, mount_point, fuse_options)
        logger.info(f"[VFS] Mounted successfully at {mount_point}")
        
        # pyfuse3.main() es una corrutina — la ejecutamos directamente ya que
        # mount_torbox_vfs corre como asyncio.Task separado (no bloquea FastAPI)
        await pyfuse3.main()
        
    except asyncio.CancelledError:
        logger.info("[VFS] Mount task cancelled")
        raise
    except Exception as e:
        logger.error(f"[VFS] Mount failed: {e}")
        raise
    finally:
        try:
            pyfuse3.close(unmount=True)
        except TypeError:
            pyfuse3.close()
        except Exception:
            pass
        try:
            import os
            os.makedirs(mount_point, exist_ok=True)
        except Exception:
            pass
        await vfs.shutdown()
