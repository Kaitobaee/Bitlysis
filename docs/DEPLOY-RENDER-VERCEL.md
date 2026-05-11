# Deploy — Render (API) + Vercel (web)

ADR 0005: API image giờ **Python-only**, không còn R/`renv`. Cold start nhanh hơn,
ít rủi ro CRAN, deploy đơn giản hơn.

## Staging URL (DoD)

| Thành phần | Placeholder | Ghi chú |
| --- | --- | --- |
| API (Render) | `https://bitlysis-api-staging.onrender.com` | Thay bằng URL thật sau khi deploy. |
| Web (Vercel) | `https://bitlysis-web-staging.vercel.app` | Thay bằng domain Vercel/custom. |

Trong **Vercel**, đặt `NEXT_PUBLIC_API_URL` = URL API Render (không slash cuối).

Trong **Render**, đặt `API_CORS_ORIGINS` = URL web Vercel + `http://localhost:3000` nếu cần dev.

## Cold start (Render free/starter)

- **Free / spin-down:** lần request đầu sau idle ~**20–40 giây** (chỉ Python; trước khi
  refactor mất 50–90s do layer R).
- **Luôn bật (paid)** hoặc **cron ping** `/health` giảm trải nghiệm "ngủ".
- **HEALTHCHECK** trong `Dockerfile` giúp orchestrator biết container sống.

## Docker (repo root)

```bash
docker build -t bitlysis-api .
docker run -p 8000:8000 -e API_CORS_ORIGINS=http://localhost:3000 bitlysis-api
```

Compose:

```bash
docker compose up -d
```

> Profile `pls-worker` đã bị bỏ trong ADR 0005 (PLS chạy in-process Python; không
> còn job R nặng cần worker RAM riêng).

## Biến môi trường — API (Render)

| Biến | Bắt buộc staging | Mô tả |
| --- | --- | --- |
| `APP_ENVIRONMENT` | Khuyến nghị `production` | Bật header/LLM an toàn hơn. |
| `API_CORS_ORIGINS` | **Có** | Danh sách origin (comma), khớp Vercel. |
| `API_TRUSTED_HOSTS` | Khuyến nghị | Ví dụ `bitlysis-api-staging.onrender.com,127.0.0.1,localhost`. |
| `UPLOAD_DIR` | Container: `/data/uploads` | Ổn định với volume Render. |
| `OPENROUTER_API_KEY` | Tùy | LLM hypothesis suggestions; không bắt buộc. |
| `RUN_ENDPOINT_TOKEN` | Khuyến nghị | Token cho `POST /v1/run` qua header `X-Run-Token`. |
| `ANALYSIS_RANDOM_SEED_DEFAULT` | Tùy | Seed bootstrap mặc định (42). |
| `PLS_BOOTSTRAP_SAMPLES_DEFAULT` | Tùy | Số mẫu bootstrap PLS-SEM (500). |
| `EXPORT_*` | Tùy | Export ZIP (Phase 8). |

Các biến `R_SUBPROCESS_TIMEOUT_SECONDS`, `R_PACKAGE_ROOT`, `BITLYSIS_RSCRIPT_PATH`
**còn trong code để backward compat** nhưng **không có tác dụng** kể từ ADR 0005.

Chi tiết đầy đủ: `services/api/.env.example`.

## Scheduled ping (GitHub Actions)

- Endpoint server-side: `POST /v1/run`.
- Workflow: `.github/workflows/r-core-schedule.yml` (giữ tên file vì lịch sử;
  payload giờ trỏ tới engine Python).
- Tạo 2 GitHub Actions secrets:
  - `RUN_ENDPOINT_URL`
  - `RUN_ENDPOINT_TOKEN`

## Biến môi trường — Web (Vercel)

| Biến | Mô tả |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL API (Render). |

## Tài liệu liên quan

- `Dockerfile` — Python-only.
- `docker-compose.yml` — local dev.
- `apps/web/vercel.json` — header tối thiểu tầng edge.
- `docs/adr/0005-python-only-stats-engine.md` — quyết định bỏ R.
- `docs/security-auditor-checklist.md` — Phase 12.
