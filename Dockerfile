# syntax=docker/dockerfile:1
# Bitlysis API image — Python-only (ADR 0005). Không còn layer R/CRAN.
# Build: docker build -t bitlysis-api .
# Context: repository root.

FROM python:3.11-slim-bookworm AS python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


FROM python-base AS api

WORKDIR /app

COPY services/api /app

RUN pip install --no-cache-dir .

RUN python -m playwright install chromium \
    && python -m playwright install-deps chromium

ENV STORAGE_BACKEND=local \
    UPLOAD_DIR=/data/uploads \
    QUEUE_BACKEND=local \
    HOST=0.0.0.0 \
    PORT=8000

RUN mkdir -p /data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
