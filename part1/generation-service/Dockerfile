FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Зависимости сервиса (включают cryptography, PyJWT и т.д.)
COPY generation-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем shared как исходники (не устанавливаем как пакет — избегаем конфликта зависимостей)
COPY shared/ /shared
ENV PYTHONPATH=/shared

# Копируем код сервиса
COPY generation-service/ .

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
