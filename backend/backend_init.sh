#!/bin/bash
set -e
echo "Starting Backend Init Script"

# Crear directorio para el mount
mkdir -p /mnt/torbox
echo "[$(date)] ✓ Directorio /mnt/torbox creado"

# El VFS custom (pyfuse3) se montará desde Python en main.py
# No necesitamos rclone
echo "[$(date)] ✓ Usando VFS custom (pyfuse3) en lugar de rclone"
echo "[$(date)] VFS se montará automáticamente cuando se inicie el backend"

# Instalar dependencias de fuse si no existen
apt-get update && apt-get install -y libfuse3-dev

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI (el VFS se monta desde main.py)
uvicorn main:app --host 0.0.0.0 --port 8000
