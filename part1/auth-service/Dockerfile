FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Копируем shared как исходники (PYTHONPATH вместо pip install /shared)
COPY shared/ /shared
ENV PYTHONPATH=/shared

# Копируем код сервиса
COPY auth-service/ .

# Генерируем RSA-ключи если не переданы через secrets
RUN mkdir -p /run/secrets && \
    python -c "\
from cryptography.hazmat.primitives.asymmetric import rsa; \
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat; \
priv = '/run/secrets/jwt_private.pem'; \
pub = '/run/secrets/jwt_public.pem'; \
key = rsa.generate_private_key(public_exponent=65537, key_size=2048); \
open(priv,'wb').write(key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())); \
open(pub,'wb').write(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)); \
print('RSA keys generated') \
"

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && python seeds/run_seeds.py && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
