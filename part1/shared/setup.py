from setuptools import setup, find_packages

setup(
    name="shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "pydantic>=2.0.0",
        "httpx>=0.26.0",
        "structlog>=24.1.0",
        "PyJWT>=2.8.0",
        "cryptography>=42.0.0",
    ],
)
