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

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI en background para poder capturar su PID
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Esperar a que uvicorn termine (o a que llegue una señal)
wait "$UVICORN_PID"
