#!/bin/bash
# Plex mount script - el VFS es montado por el backend
# Solo necesitamos preparar el directorio

if ! command -v fuse &> /dev/null; then
    echo "Installing fuse..."
    apt-get update && apt-get install -y libfuse3-0
fi

# Crear directorio si no existe
mkdir -p /mnt/torbox

echo "✓ Mount point /mnt/torbox preparado"
echo "✓ Esperando a que el backend monte el VFS..."

# El VFS será montado desde el backend
# Solo iniciar Plex
exec "$@"
