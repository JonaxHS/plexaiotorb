#!/bin/bash
set -e
echo "Starting Backend Init Script"

# Crear directorio para el mount
mkdir -p /mnt/torbox
echo "[$(date)] ✓ Directorio /mnt/torbox creado"

# El VFS custom (pyfuse3) se montará desde Python en main.py
echo "[$(date)] ✓ Usando VFS custom (pyfuse3)"
echo "[$(date)] VFS se montará automáticamente cuando se inicie el backend"

# Validar pyfuse3 (autorreparación por si el contenedor viejo no lo trae)
if python -c "import pyfuse3" >/dev/null 2>&1; then
	echo "[$(date)] ✓ pyfuse3 disponible"
else
	echo "[$(date)] ⚠️ pyfuse3 no encontrado, instalando en runtime..."
	echo "[$(date)] Instalando dependencias de compilación para pyfuse3 (pkg-config, build-essential, libfuse3-dev)..."
	apt-get update && apt-get install -y --no-install-recommends \
		pkg-config \
		build-essential \
		libfuse3-dev
	pip install --no-cache-dir pyfuse3 || {
		echo "[$(date)] ✗ No se pudo instalar pyfuse3"
		exit 1
	}
	python -c "import pyfuse3" >/dev/null 2>&1 || {
		echo "[$(date)] ✗ pyfuse3 sigue sin estar disponible después de instalar"
		exit 1
	}
	echo "[$(date)] ✓ pyfuse3 instalado correctamente"
fi

echo "[$(date)] Iniciando FastAPI..."
# Iniciar FastAPI (el VFS se monta desde main.py)
uvicorn main:app --host 0.0.0.0 --port 8000
