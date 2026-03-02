"""
Integration point para montar el VFS desde FastAPI.
"""
import asyncio
import logging
import os
from typing import Optional
from vfs import mount_torbox_vfs

logger = logging.getLogger(__name__)

class VFSManager:
    """Maneja el ciclo de vida del VFS"""
    
    def __init__(self):
        self.mount_task: Optional[asyncio.Task] = None
        self.torbox_url = os.getenv("TORBOX_URL", "http://localhost:8080")
        self.torbox_user = os.getenv("TORBOX_USER", "")
        self.torbox_pass = os.getenv("TORBOX_PASS", "")
        self.mount_point = os.getenv("MOUNT_POINT", "/mnt/torbox")
    
    async def start(self):
        """Inicia el VFS"""
        logger.info("[VFSManager] Starting...")
        
        if not all([self.torbox_url, self.torbox_user, self.torbox_pass]):
            logger.warning("[VFSManager] TorBox credentials not configured, VFS disabled")
            return
        
        try:
            # Crear directorio si no existe
            os.makedirs(self.mount_point, exist_ok=True)
            
            # Montar VFS
            self.mount_task = asyncio.create_task(
                mount_torbox_vfs(
                    self.torbox_url,
                    self.torbox_user,
                    self.torbox_pass,
                    self.mount_point
                )
            )
            logger.info(f"[VFSManager] VFS mounting at {self.mount_point}")
            
        except Exception as e:
            logger.error(f"[VFSManager] Failed to start VFS: {e}")
    
    async def stop(self):
        """Para el VFS"""
        logging.info("[VFSManager] Stopping...")
        
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
    await vfs_manager.start()

async def shutdown_vfs():
    """Llamar desde FastAPI shutdown"""
    await vfs_manager.stop()
