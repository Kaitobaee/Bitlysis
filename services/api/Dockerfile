# syntax=docker/dockerfile:1
# Python API image with Playwright Chromium for website screenshot capture.

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STORAGE_BACKEND=local \
    UPLOAD_DIR=/data/uploads \
    QUEUE_BACKEND=local \
    HOST=0.0.0.0 \
    PORT=8000 \
    # Playwright: dùng Chromium bundled, không cần Chrome hệ thống
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# --- System dependencies ---
# Chromium/Playwright cần một số thư viện hệ thống trên Debian Bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        # Chromium runtime deps
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxcb1 \
        libxkbcommon0 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
        fonts-liberation \
        fonts-noto-color-emoji \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/api /app

# --- Install Python packages ---
RUN pip install --no-cache-dir .

# --- Install Playwright Chromium browser ---
# Chỉ cài Chromium (nhỏ hơn Firefox/WebKit)
RUN python -m playwright install chromium \
    && python -m playwright install-deps chromium

RUN mkdir -p /data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
