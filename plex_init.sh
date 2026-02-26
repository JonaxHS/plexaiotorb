#!/bin/bash
# Install rclone and fuse if they don't exist
if ! command -v rclone &> /dev/null; then
    echo "Installing rclone and fuse in Plex container..."
    apt-get update && apt-get install -y rclone fuse
fi

# Give it a second just in case
sleep 2

# Check if config exists and torbox remote is defined
if grep -q "\[torbox\]" /rclone_config/rclone.conf 2>/dev/null; then
    # Unmount if already mounted
    umount -f /mnt/torbox 2>/dev/null || true
    
    # Needs to be created
    mkdir -p /mnt/torbox
    
    echo "Mounting torbox WebDAV inside Plex container natively..."
    rclone mount torbox: /mnt/torbox \
        --config /rclone_config/rclone.conf \
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
        --daemon
else
    echo "rclone.conf not completely set up yet. Skipping mount until backend configures it (checked /rclone_config/rclone.conf)."
fi
