#!/bin/bash
set -e

echo "======================================"
echo " PlexAioTorb - Linux VPS Installer"
echo "======================================"

# 1. Check Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
fi

echo "Creating necessary configuration folders..."
mkdir -p app_config
mkdir -p rclone_config
mkdir -p plex_config
mkdir -p plex_media/movies
mkdir -p plex_media/tv

# 2. Check Torbox Data Volume
if ! docker volume ls | grep -q "torbox_data"; then
    echo "Creating Docker Volume torbox_data..."
    docker volume create torbox_data
fi

# 3. Create .env if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo "Creating empty .env file..."
    mkdir -p backend
    touch backend/.env
fi

# 4. Starting stack
echo "Starting PlexAioTorb containers..."
docker compose up -d --build

echo ""
echo "======================================"
echo " Installation Complete!"
echo " Access the Web UI at http://<YOUR-VPS-IP>:5173"
echo " Access Plex at http://<YOUR-VPS-IP>:32400/web"
echo "======================================"
