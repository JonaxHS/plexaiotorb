FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Dependencias de sistema mínimas para backend API
RUN apt-get update && apt-get install -y \
    procps \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# We'll volume mount the code in dev for live reload, but copy the rest just in case
COPY . .

RUN chmod +x /app/backend_init.sh
CMD ["/app/backend_init.sh"]
