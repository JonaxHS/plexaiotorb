#!/bin/bash
set -e
echo "Starting Backend Init Script"

# Crear directorio para el mount
mkdir -p /mnt/torbox
echo "[$(date)] ✓ Directorio /mnt/torbox creado"

# El VFS custom (pyfuse3) se montará desde Python en main.py
echo "[$(date)] ✓ Usando VFS custom (pyfuse3)"
echo "[$(date)] VFS se montará automáticamente cuando se inicie el backend"

# Función de limpieza al recibir señales de stop (SIGTERM/SIGINT)
cleanup() {
    echo "[$(date)] ⚡ Señal recibida, desmontando VFS y cerrando..."
    # Forzar desmontaje del punto FUSE para liberar al kernel
    fusermount3 -uz /mnt/torbox 2>/dev/null || umount -l /mnt/torbox 2>/dev/null || true
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

# Validar dependencias VFS (autorreparación)
if python -c "import pyfuse3, aiohttp, lxml" >/dev/null 2>&1; then
	echo "[$(date)] ✓ Dependencias VFS disponibles (pyfuse3, aiohttp, lxml)"
else
	echo "[$(date)] ⚠️ Dependencias VFS faltantes, instalando en runtime..."
	apt-get update && apt-get install -y --no-install-recommends \
		pkg-config \
		build-essential \
		libfuse3-dev
	pip install --no-cache-dir -r /app/requirements.txt || {
		echo "[$(date)] ✗ No se pudieron instalar las dependencias VFS"
		exit 1
	}
fi

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI en background para poder capturar su PID
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Esperar a que uvicorn termine (o a que llegue una señal)
wait "$UVICORN_PID"
