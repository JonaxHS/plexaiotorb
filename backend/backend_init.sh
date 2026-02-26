#!/bin/bash
echo "Starting Backend Init Script"

if grep -q "\[torbox\]" /app/rclone_config/rclone.conf 2>/dev/null; then
    # Unmount if already mounted
    umount -f /mnt/torbox 2>/dev/null || true
    
    mkdir -p /mnt/torbox
    
    echo "Mounting torbox WebDAV inside Backend container natively..."
    rclone mount torbox: /mnt/torbox --config /app/rclone_config/rclone.conf --vfs-cache-mode full --allow-non-empty --allow-other --dir-cache-time 5s --attr-timeout 2s --rc --rc-addr 127.0.0.1:5572 &
else
    echo "rclone.conf not completely set up yet. Skipping mount until configured."
fi

# Finally, start the FastAPI app
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
