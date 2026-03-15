FROM python:3.12-slim

WORKDIR /app

# Устанавливаем системные зависимости для python-docx и minio
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем shared-пакет
# Контекст сборки — part1/ (docker-compose build context: ../), поэтому пути относительны part1/
COPY shared/ /shared
RUN pip install --no-cache-dir /shared

# Устанавливаем зависимости сервиса
COPY generation-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY generation-service/ .

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8003/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
