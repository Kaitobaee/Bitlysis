# syntax=docker/dockerfile:1
# Phase 11 — API image: tách layer Python base vs R+CRAN để cache; HEALTHCHECK /health.
# Build: docker build -t bitlysis-api .
# Context: repository root (cần packages/r-pipeline + services/api).

FROM python:3.12-slim-bookworm AS python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


FROM python-base AS r-layer

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        r-base \
        r-base-dev \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY packages/r-pipeline /opt/bitlysis/packages/r-pipeline

ENV R_PACKAGE_ROOT=/opt/bitlysis/packages/r-pipeline

RUN Rscript /opt/bitlysis/packages/r-pipeline/tools/ci_install.R


FROM r-layer AS api

WORKDIR /app

COPY services/api /app

RUN pip install --no-cache-dir .

ENV STORAGE_BACKEND=local \
    UPLOAD_DIR=/data/uploads \
    QUEUE_BACKEND=local \
    HOST=0.0.0.0 \
    PORT=8000

RUN mkdir -p /data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Profile PLS: cùng image; trên Render hãy tạo service thứ hai với RAM lớn hơn và trỏ CORS/load balancer nội bộ.
# docker build --target api -t bitlysis-api .
FROM api AS pls-worker

ENV BITLYSIS_PLS_WORKER_ROLE=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
