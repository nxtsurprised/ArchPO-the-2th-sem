FROM python:3.12-slim

WORKDIR /app

# Зависимости сервиса (включают cryptography и т.д.)
COPY catalog-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем shared как исходники (PYTHONPATH вместо pip install /shared)
COPY shared/ /shared
ENV PYTHONPATH=/shared

# Копируем код сервиса
COPY catalog-service/ .

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
