#!/bin/bash
echo "Starting Backend Init Script"

if grep -q "\[torbox\]" /app/rclone_config/rclone.conf 2>/dev/null; then
    # Unmount if already mounted
    umount -f /mnt/torbox 2>/dev/null || true
    
    mkdir -p /mnt/torbox
    
    echo "Mounting torbox WebDAV inside Backend container natively..."
    rclone mount torbox: /mnt/torbox \
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
        --rc-addr 127.0.0.1:5572 &
else
    echo "rclone.conf not completely set up yet. Skipping mount until configured."
fi

# Finally, start the FastAPI app
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
