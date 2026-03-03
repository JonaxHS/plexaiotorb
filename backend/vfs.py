"""
VFS Custom basado en pyfuse3 con cliente WebDAV sincrónico.
"""
import pyfuse3
import logging
import asyncio
from typing import Dict, Optional
from stat import S_IFREG, S_IFDIR
import errno
from vfs_client import TorBoxWebDAVClient, VFSFile

logger = logging.getLogger(__name__)


class TorBoxVFS(pyfuse3.Operations):
    """VFS para montar TorBox via pyfuse3. Usa cliente WebDAV sincrónico."""

    def __init__(self, torbox_url: str, torbox_user: str, torbox_pass: str):
        super().__init__()
        self.client = TorBoxWebDAVClient(torbox_url, torbox_user, torbox_pass)
        self._inode_map: Dict[int, str] = {pyfuse3.ROOT_INODE: "/"}
        self._path_to_inode: Dict[str, int] = {"/": pyfuse3.ROOT_INODE}
        self._next_inode = pyfuse3.ROOT_INODE + 1

    def _get_inode(self, path: str) -> int:
        path = path.rstrip('/') or '/'
        if path in self._path_to_inode:
            return self._path_to_inode[path]
        inode = self._next_inode
        self._next_inode += 1
        self._inode_map[inode] = path
        self._path_to_inode[path] = inode
        return inode

    def _get_path(self, inode: int) -> str:
        return self._inode_map.get(inode, "/")

    def _make_attr(self, inode: int, is_dir: bool, size: int = 0, mtime: float = None):
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

        for field_name, field_value in (
            ("st_atime_ns", ts_ns),
            ("st_mtime_ns", ts_ns),
            ("st_ctime_ns", ts_ns),
        ):
            try:
                setattr(attr, field_name, field_value)
            except Exception:
                pass

        attr.generation = 0
        attr.entry_timeout = 60
        attr.attr_timeout = 60
        return attr

    def _make_entry_attr(self, file_info: VFSFile):
        inode = self._get_inode(file_info.path.rstrip('/') if not file_info.is_dir else file_info.path)
        return self._make_attr(inode, file_info.is_dir, file_info.size, file_info.mtime.timestamp())

    async def lookup(self, parent_inode, name, ctx=None):
        parent_path = self._get_path(parent_inode)
        name_str = name.decode() if isinstance(name, bytes) else name
        path = f"/{name_str}" if parent_path == "/" else f"{parent_path}/{name_str}"

        try:
            file_info = self.client.get_file_info(path)
            if not file_info:
                raise pyfuse3.FUSEError(errno.ENOENT)
            return self._make_entry_attr(file_info)
        except pyfuse3.FUSEError:
            raise
        except Exception as e:
            logger.debug(f"[VFS] lookup error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.ENOENT)

    async def readdir(self, inode, offset, token):
        path = self._get_path(inode)

        try:
            files = self.client.list_dir(path)

            entries = []
            dot_inode = inode
            dotdot_inode = self._inode_map.get(inode - 1, pyfuse3.ROOT_INODE)
            if pyfuse3.ROOT_INODE in self._inode_map:
                dotdot_inode = pyfuse3.ROOT_INODE

            entries.append((b'.', self._make_attr(dot_inode, True, 0), 1))
            entries.append((b'..', self._make_attr(dotdot_inode, True, 0), 2))

            for i, file_info in enumerate(files, start=3):
                file_inode = self._get_inode(
                    file_info.path.rstrip('/') if not file_info.is_dir else file_info.path
                )
                attr = self._make_entry_attr(file_info)
                entries.append((file_info.name.encode(), attr, i + offset))

            for name_bytes, attr, off in entries[offset:]:
                if not pyfuse3.readdir_reply(token, name_bytes, attr, off):
                    break

        except Exception as e:
            logger.error(f"[VFS] readdir error for {path}: {e}")

    async def getattr(self, inode, ctx=None):
        path = self._get_path(inode)

        if inode == pyfuse3.ROOT_INODE:
            return self._make_attr(inode, True, 0)

        try:
            file_info = self.client.get_file_info(path)
            if not file_info:
                raise pyfuse3.FUSEError(errno.ENOENT)
            return self._make_attr(inode, file_info.is_dir, file_info.size, file_info.mtime.timestamp())
        except pyfuse3.FUSEError:
            raise
        except Exception as e:
            logger.debug(f"[VFS] getattr error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.ENOENT)

    async def open(self, inode, flags, ctx=None):
        return pyfuse3.FileInfo(fh=inode)

    async def read(self, fh, offset, size):
        path = self._get_path(fh)
        try:
            return self.client.read_file(path, offset, size)
        except Exception as e:
            logger.error(f"[VFS] read error for {path}: {e}")
            raise pyfuse3.FUSEError(errno.EIO)


def _run_fuse_in_thread(torbox_url: str, torbox_user: str, torbox_pass: str, mount_point: str):
    """
    Ejecuta todo el ciclo de vida de FUSE en un hilo sincrónico.
    pyfuse3 usa trio, esto corre trio.run() en el hilo del threadpool.
    """
    import trio

    vfs = TorBoxVFS(torbox_url, torbox_user, torbox_pass)
    vfs.client.connect()

    # Pre-poblar la caché ANTES de que FUSE empiece a aceptar peticiones.
    # Si TorBox está rate-limiting, reintentamos con backoff hasta 3 veces.
    import time
    for warmup_attempt in range(3):
        logger.info(f"[VFS] Pre-cargando directorio raíz (intento {warmup_attempt+1}/3)...")
        root_files = vfs.client.list_dir("/")
        if root_files:
            logger.info(f"[VFS] ✓ Caché pre-cargada: {len(root_files)} ítems en /")
            break
        else:
            wait = (warmup_attempt + 1) * 15  # 15s, 30s, 45s
            logger.warning(f"[VFS] Raíz vacía o rate-limited, reintentando en {wait}s...")
            time.sleep(wait)

    fuse_options = set(pyfuse3.default_options)
    fuse_options.add("fsname=torbox_vfs")
    fuse_options.add("allow_other")

    try:
        pyfuse3.init(vfs, mount_point, fuse_options)
        logger.info(f"[VFS] Mounted successfully at {mount_point}")
        trio.run(pyfuse3.main)
    except Exception as e:
        logger.error(f"[VFS] FUSE thread error: {e}")
        raise
    finally:
        try:
            pyfuse3.close(unmount=True)
        except TypeError:
            pyfuse3.close()
        except Exception:
            pass
        vfs.client.disconnect()
        logger.info("[VFS] FUSE thread exited")


async def mount_torbox_vfs(torbox_url: str, torbox_user: str, torbox_pass: str, mount_point: str):
    """
    Inicia el VFS de TorBox en un hilo de fondo.
    pyfuse3.init() y pyfuse3.main() corren juntos en un hilo (via asyncio.to_thread)
    para evitar el deadlock causado por dividirlos en contextos distintos.
    """
    logger.info(f"[VFS] Starting TorBox VFS at {mount_point}")
    await asyncio.to_thread(_run_fuse_in_thread, torbox_url, torbox_user, torbox_pass, mount_point)
