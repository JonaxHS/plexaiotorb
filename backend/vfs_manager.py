"""
Integration point para montar el VFS desde FastAPI.
"""
import logging
import os

logger = logging.getLogger(__name__)

class VFSManager:
    """Maneja el ciclo de vida del mount externo (torbox-media-center)."""
    
    def __init__(self):
        self.mount_point = os.getenv("MOUNT_POINT", "/mnt/torbox")
    
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
        """Prepara el punto de montaje externo. El montaje real lo hace torbox-media-center."""
        logger.info("[VFSManager] External-only mode: torbox-media-center")
        os.makedirs(self.mount_point, exist_ok=True)
        return True
    
    async def stop(self):
        """No-op para compatibilidad: no hay FUSE interno que detener."""
        logger.info("[VFSManager] Stopping...")
        logger.info("[VFSManager] External-only mode active, nothing to stop")

# Global instance
vfs_manager = VFSManager()

async def startup_vfs():
    """Llamar desde FastAPI startup"""
    return await vfs_manager.start()

async def shutdown_vfs():
    """Llamar desde FastAPI shutdown"""
    await vfs_manager.stop()
