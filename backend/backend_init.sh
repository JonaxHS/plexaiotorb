#!/bin/bash
set -e
echo "Starting Backend Init Script"

# Crear directorio para el mount
mkdir -p /mnt/torbox
echo "[$(date)] ✓ Directorio /mnt/torbox creado"

# VFS externo (torbox-media-center) se monta desde Docker Compose
echo "[$(date)] ✓ Usando VFS externo (torbox-media-center)"
echo "[$(date)] Backend esperará a que torbox-media-center esté listo para montar"

# Función de limpieza al recibir señales de stop (SIGTERM/SIGINT)
cleanup() {
    echo "[$(date)] ⚡ Señal recibida, cerrando..."
    # Matar uvicorn si sigue corriendo
    if [ -n "$UVICORN_PID" ]; then
        kill -SIGINT "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
    echo "[$(date)] ✓ Limpieza completada"
    exit 0
}

# Registrar el manejador de señales
trap cleanup SIGTERM SIGINT
echo "[$(date)] Esperando a que el mount de TorBox esté listo..."
for i in {1..60}; do
    if [ -d "$TORBOX_MOUNT" ] && [ "$(ls -A $TORBOX_MOUNT 2>/dev/null)" ]; then
        echo "[$(date)] ✓ Mount de TorBox está listo"
        break
    fi
    echo "[$(date)] Esperando... ($i/60)"
    sleep 2
done

# Start VFS daemon in background
echo "[$(date)] Iniciando TorBox VFS daemon..."
python3 /app/torbox_vfs_mount.py \
    --mount-source="$TORBOX_MOUNT" \
    --vfs-mount="$VFS_MOUNT" \
    --cache-dir="$VFS_CACHE" &

VFS_PID=$!
echo "[$(date)] VFS daemon PID: $VFS_PID"

# Wait for VFS mount to become ready
echo "[$(date)] Esperando a que el mount del VFS aparezca..."
for i in {1..30}; do
    if mountpoint -q "$VFS_MOUNT"; then
        echo "[$(date)] ✓ Mount del VFS está listo"
        break
    fi
    echo "[$(date)] Esperando... ($i/30)"
    sleep 1
done

if ! mountpoint -q "$VFS_MOUNT"; then
    echo "[$(date)] ERROR: El mount del VFS no apareció!"
    kill $VFS_PID || true
    exit 1
fi

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI en background para poder capturar su PID
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Esperar a que uvicorn termine (o a que llegue una señal)
wait "$UVICORN_PID"

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI en background para poder capturar su PID
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Esperar a que uvicorn termine (o a que llegue una señal)
wait "$UVICORN_PID"
