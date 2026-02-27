#!/bin/bash
set -e
echo "Starting Backend Init Script"

if grep -q "\[torbox\]" /app/rclone_config/rclone.conf 2>/dev/null; then
    # Unmount if already mounted
    umount -f /mnt/torbox 2>/dev/null || true
    
    mkdir -p /mnt/torbox
    
    echo "[$(date)] Montando torbox WebDAV dentro del contenedor Backend..."
    nohup rclone mount torbox: /mnt/torbox \
        --config /app/rclone_config/rclone.conf \
        --vfs-cache-mode full \
        --vfs-cache-max-age 24h \
        --vfs-cache-max-size 10G \
        --vfs-read-chunk-size 128M \
        --vfs-read-chunk-size-limit off \
        --buffer-size 32M \
        --dir-cache-time 1000h \
        --attr-timeout 1000h \
        --allow-non-empty \
        --allow-other \
        --rc \
        --rc-addr 127.0.0.1:5572 \
        > /tmp/rclone.log 2>&1 &
    
    echo "[$(date)] Esperando a que rclone responda..."
    sleep 3
    
    # Esperar hasta 15 segundos a que rclone RC esté disponible
    for i in {1..5}; do
        if curl -s http://127.0.0.1:5572/rc/stats > /dev/null 2>&1; then
            echo "[$(date)] ✓ Rclone montado exitosamente en /mnt/torbox con RC activo"
            break
        fi
        if [ $i -lt 5 ]; then
            echo "[$(date)] Reintentando conexión a rclone RC... ($((i * 3))s)"
            sleep 3
        fi
    done
else
    echo "[$(date)] ADVERTENCIA: rclone.conf no está configurado. Continuando sin montaje."
fi

# Iniciar FastAPI (sin exec para mantener rclone vivo)
echo "[$(date)] Iniciando FastAPI en puerto 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
