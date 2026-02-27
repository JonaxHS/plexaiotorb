#!/bin/bash
set -e
echo "Starting Backend Init Script"

# Crear directorio incluso si no vamos a montar
mkdir -p /mnt/torbox
echo "[$(date)] ✓ Directorio /mnt/torbox creado"

if grep -q "\[torbox\]" /app/rclone_config/rclone.conf 2>/dev/null; then
    echo "[$(date)] ✓ Configuración [torbox] encontrada en rclone.conf"
    
    # Unmount if already mounted
    umount -f /mnt/torbox 2>/dev/null || true
    
    echo "[$(date)] Montando torbox WebDAV dentro del contenedor Backend..."
    nohup rclone mount torbox: /mnt/torbox \
        --config /app/rclone_config/rclone.conf \
        --vfs-cache-mode writes \
        --vfs-cache-max-age 24h \
        --vfs-cache-max-size 50G \
        --vfs-read-chunk-size 256M \
        --vfs-read-chunk-size-limit off \
        --buffer-size 64M \
        --dir-cache-time 100h \
        --attr-timeout 100h \
        --vfs-read-wait 5ms \
        --vfs-write-wait 5ms \
        --vfs-fast-fingerprint \
        --allow-non-empty \
        --allow-other \
        --rc \
        --rc-addr 127.0.0.1:5572 \
        --log-level INFO \
        > /tmp/rclone.log 2>&1 &
    
    echo "[$(date)] Esperando a que rclone responda..."
    sleep 5
    
    # Esperar hasta 20 segundos a que rclone RC esté disponible Y tenga items
    for i in {1..10}; do
        if curl -s http://127.0.0.1:5572/rc/stats > /dev/null 2>&1; then
            # RC responde, verificar que haya items en el mount
            item_count=$(ls /mnt/torbox 2>/dev/null | wc -l)
            if [ "$item_count" -gt 0 ]; then
                echo "[$(date)] ✓ Rclone montado exitosamente en /mnt/torbox con RC activo ($item_count items)"
                break
            else
                echo "[$(date)] RC activo pero esperando items... ($((i * 2))s)"
            fi
        else
            echo "[$(date)] RC no responde aún... intento $i/10"
        fi
        if [ $i -lt 10 ]; then
            sleep 2
        fi
    done
else
    echo "[$(date)] ⚠️ ADVERTENCIA: rclone.conf no contiene [torbox]. Verificar:"
    echo "[$(date)]   - /app/rclone_config/rclone.conf existe?"
    if [ -f /app/rclone_config/rclone.conf ]; then
        echo "[$(date)]   ✓ Archivo existe"
        echo "[$(date)]   Contenido:"
        cat /app/rclone_config/rclone.conf | head -20
    else
        echo "[$(date)]   ✗ Archivo NO existe"
    fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
