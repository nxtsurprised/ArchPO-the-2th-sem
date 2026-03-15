FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY catalog-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install shared package (build context = part1/)
COPY shared/ /shared
RUN pip install --no-cache-dir -e /shared

# Copy application code
COPY catalog-service/ .

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8002/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
