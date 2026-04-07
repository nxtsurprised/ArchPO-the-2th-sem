# Используем официальный образ Playwright — браузеры уже установлены
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/outputs

EXPOSE 8006

HEALTHCHECK --interval=20s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8006/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "1"]
