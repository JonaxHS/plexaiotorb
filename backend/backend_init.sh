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
    
    RCLONE_PID=$!
    echo "[$(date)] Rclone PID: $RCLONE_PID"
    
    # Esperar a que rclone se monte correctamente
    sleep 3
    
    # Intentar conectar a rclone rc para verificar que está activo
    if curl -s http://127.0.0.1:5572/rc/stats > /dev/null 2>&1; then
        echo "[$(date)] ✓ Rclone montado exitosamente en /mnt/torbox con RC activo"
    elif [ -d /mnt/torbox ] && [ $(ls /mnt/torbox 2>/dev/null | wc -l) -ge 0 ]; then
        echo "[$(date)] ✓ Rclone montado exitosamente en /mnt/torbox ($(ls /mnt/torbox | wc -l) items)"
    else
        echo "[$(date)] ✗ CRÍTICO: Rclone no se inició. Ver /tmp/rclone.log"
        tail -20 /tmp/rclone.log
        exit 1
    fi
else
    echo "[$(date)] ADVERTENCIA: rclone.conf no está configurado. Continuando sin montaje."
fi

# Iniciar FastAPI (sin exec para mantener rclone vivo)
echo "[$(date)] Iniciando FastAPI en puerto 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
