FROM python:3.12-slim

# Playwright и браузеры устанавливаются только для подключения через CDP
# Реальный браузер работает в отдельном контейнере playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Python client (без установки браузеров — браузер в отдельном контейнере)
RUN pip install --no-cache-dir playwright==1.41.2

COPY . .

# Создаём директорию для выходных файлов ПМИ
RUN mkdir -p /app/outputs

EXPOSE 8006

HEALTHCHECK --interval=20s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8006/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "1"]
