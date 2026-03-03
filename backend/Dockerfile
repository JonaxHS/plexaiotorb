FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema para fuse y pyfuse3
RUN apt-get update && apt-get install -y \
    libfuse3-dev \
    pkg-config \
    build-essential \
    procps \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    python -c "import pyfuse3; print('pyfuse3 OK')"

# We'll volume mount the code in dev for live reload, but copy the rest just in case
COPY . .

RUN chmod +x /app/backend_init.sh
CMD ["/app/backend_init.sh"]
