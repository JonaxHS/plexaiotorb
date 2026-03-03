"""
Integration point para montar el VFS desde FastAPI.
"""
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class VFSManager:
    """Maneja el ciclo de vida del VFS"""
    
    def __init__(self):
        self.mount_task: Optional[asyncio.Task] = None
        self.mount_point = os.getenv("MOUNT_POINT", "/mnt/torbox")

    def get_provider(self) -> str:
        """Obtiene el proveedor de montaje: internal o torbox-media-center."""
        try:
            from config import config
            configured = (config.get("vfs", {}).get("provider") or "").strip().lower()
        except Exception:
            configured = ""

        env_provider = (os.getenv("VFS_PROVIDER", "") or "").strip().lower()
        provider = env_provider or configured or "internal"

        aliases = {
            "external": "torbox-media-center",
            "torbox_media_center": "torbox-media-center",
            "torbox-media-center": "torbox-media-center",
            "internal": "internal",
            "pyfuse3": "internal",
            "disabled": "disabled",
        }
        return aliases.get(provider, provider)
    
    def load_credentials(self):
        """Carga credenciales de config.yaml o variables de entorno"""
        try:
            from config import config
            
            # Intentar desde config.yaml primero
            torbox_url = config.get("vfs", {}).get("torbox_url") or os.getenv("TORBOX_URL")
            torbox_user = config.get("vfs", {}).get("torbox_user") or os.getenv("TORBOX_USER")
            torbox_pass = config.get("vfs", {}).get("torbox_pass") or os.getenv("TORBOX_PASS")
            
            return torbox_url, torbox_user, torbox_pass
        except Exception as e:
            logger.warning(f"[VFSManager] Error loading config: {e}")
            # Fallback a env vars
            return (
                os.getenv("TORBOX_URL", ""),
                os.getenv("TORBOX_USER", ""),
                os.getenv("TORBOX_PASS", "")
            )
    
    async def start(self):
        """Inicia el VFS"""
        logger.info("[VFSManager] Starting...")

        provider = self.get_provider()
        if provider == "disabled":
            logger.info("[VFSManager] VFS provider=disabled. Se omite montaje.")
            return False

        if provider == "torbox-media-center":
            logger.info("[VFSManager] VFS provider=torbox-media-center. Se usa mount externo en %s", self.mount_point)
            os.makedirs(self.mount_point, exist_ok=True)
            return False

        if provider != "internal":
            logger.warning("[VFSManager] Proveedor VFS desconocido '%s'. Usando internal.", provider)
        
        torbox_url, torbox_user, torbox_pass = self.load_credentials()
        
        if not all([torbox_url, torbox_user, torbox_pass]):
            logger.warning("[VFSManager] TorBox credentials not configured, VFS disabled")
            logger.warning(f"  TORBOX_URL: {'✓' if torbox_url else '✗'}")
            logger.warning(f"  TORBOX_USER: {'✓' if torbox_user else '✗'}")
            logger.warning(f"  TORBOX_PASS: {'✓' if torbox_pass else '✗'}")
            return False
        
        try:
            try:
                from vfs import mount_torbox_vfs
            except ModuleNotFoundError as e:
                logger.error(f"[VFSManager] VFS disabled: missing dependency ({e})")
                logger.error("[VFSManager] Instala dependencias VFS (pyfuse3/aiohttp/lxml) y reconstruye: docker compose up -d --build")
                return False

            # Crear directorio si no existe
            os.makedirs(self.mount_point, exist_ok=True)
            
            # Montar VFS
            self.mount_task = asyncio.create_task(
                mount_torbox_vfs(
                    torbox_url,
                    torbox_user,
                    torbox_pass,
                    self.mount_point
                )
            )
            logger.info(f"[VFSManager] VFS mounting at {self.mount_point}")
            return True
            
        except Exception as e:
            logger.error(f"[VFSManager] Failed to start VFS: {e}")
            return False
    
    async def stop(self):
        """Para el VFS"""
        logger.info("[VFSManager] Stopping...")

        provider = self.get_provider()
        if provider != "internal":
            logger.info("[VFSManager] Provider externo/disabled, no hay FUSE interno que detener")
            return

        try:
            import pyfuse3
            pyfuse3.terminate()
        except Exception:
            pass
        
        if self.mount_task:
            self.mount_task.cancel()
            try:
                await self.mount_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[VFSManager] Error stopping VFS: {e}")

# Global instance
vfs_manager = VFSManager()

async def startup_vfs():
    """Llamar desde FastAPI startup"""
    return await vfs_manager.start()

async def shutdown_vfs():
    """Llamar desde FastAPI shutdown"""
    await vfs_manager.stop()
