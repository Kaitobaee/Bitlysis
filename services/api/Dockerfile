# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STORAGE_BACKEND=local \
    UPLOAD_DIR=/data/uploads \
    QUEUE_BACKEND=local \
    HOST=0.0.0.0 \
    PORT=8000 \
    R_PACKAGE_ROOT=/opt/bitlysis/packages/r-pipeline

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libnode-dev \
        r-base \
        r-base-dev \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/bitlysis

# This Dockerfile expects Render dockerContext = repository root.
COPY packages/r-pipeline /opt/bitlysis/packages/r-pipeline
RUN Rscript /opt/bitlysis/packages/r-pipeline/tools/ci_install.R

WORKDIR /app
COPY services/api /app

RUN pip install --no-cache-dir .
RUN mkdir -p /data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
