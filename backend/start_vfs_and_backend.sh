#!/bin/bash
# Start TorBox VFS mount and backend

set -e

TORBOX_MOUNT="${MOUNT_POINT:-/mnt/torbox}"
VFS_MOUNT="${VFS_MOUNT:-/mnt/torbox_vfs}"
VFS_CACHE="${VFS_CACHE:-/tmp/torbox_cache}"

echo "[Init] Setting up TorBox VFS mount..."
echo "[Init] TorBox source: $TORBOX_MOUNT"
echo "[Init] VFS mount point: $VFS_MOUNT"
echo "[Init] Cache directory: $VFS_CACHE"

# Create mount point directories
mkdir -p "$VFS_MOUNT"
mkdir -p "$VFS_CACHE"

# Check if TorBox mount is ready
echo "[Init] Waiting for TorBox mount to be ready..."
for i in {1..30}; do
    if [ -d "$TORBOX_MOUNT" ] && [ "$(ls -A $TORBOX_MOUNT 2>/dev/null)" ]; then
        echo "[Init] ✓ TorBox mount is ready (entries found)"
        break
    fi
    echo "[Init] Waiting... ($i/30)"
    sleep 2
done

# Start VFS mount in background
echo "[Init] Starting TorBox VFS daemon..."
python3 /app/torbox_vfs_mount.py \
    --mount-source="$TORBOX_MOUNT" \
    --vfs-mount="$VFS_MOUNT" \
    --cache-dir="$VFS_CACHE" &

VFS_PID=$!
echo "[Init] VFS daemon PID: $VFS_PID"

# Wait for VFS to mount
echo "[Init] Waiting for VFS mount to appear..."
for i in {1..30}; do
    if mountpoint -q "$VFS_MOUNT"; then
        echo "[Init] ✓ VFS mount is ready"
        break
    fi
    echo "[Init] Waiting... ($i/30)"
    sleep 1
done

if ! mountpoint -q "$VFS_MOUNT"; then
    echo "[Init] ERROR: VFS mount failed to appear!"
    kill $VFS_PID || true
    exit 1
fi

# Start backend FastAPI
echo "[Init] Starting backend..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
