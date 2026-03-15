FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared /shared
RUN pip install --no-cache-dir -e /shared

COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth-service/ .

# Generate RSA keys if not provided
RUN mkdir -p /run/secrets && \
    python -c "\
from cryptography.hazmat.primitives.asymmetric import rsa; \
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat; \
import os; \
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
