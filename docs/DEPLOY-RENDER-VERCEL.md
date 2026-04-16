# Deploy — Render (API) + Vercel (web)

Phase 11 — infra; cập nhật URL staging khi bạn đã tạo service.

## Staging URL (DoD)

| Thành phần | Placeholder | Ghi chú |
| --- | --- | --- |
| API (Render) | `https://bitlysis-api-staging.onrender.com` | Thay bằng URL thật sau khi deploy. |
| Web (Vercel) | `https://bitlysis-web-staging.vercel.app` | Thay bằng domain Vercel/custom. |

Trong **Vercel**, đặt `NEXT_PUBLIC_API_URL` = URL API Render (không slash cuối).

Trong **Render**, đặt `API_CORS_ORIGINS` = URL web Vercel + `http://localhost:3000` nếu cần dev.

## Cold start (Render free/starter)

- **Free / spin-down:** lần request đầu sau idle có thể mất **~50–90 giây** (pull image + khởi động Python + R layer).
- **Luôn bật (paid)** hoặc **cron ping** `/health` giảm trải nghiệm “ngủ”.
- **HEALTHCHECK** trong `Dockerfile` giúp orchestrator biết container sống; Render dùng `healthCheckPath: /health` trong `render.yaml`.

## Docker (repo root)

```bash
docker build -t bitlysis-api .
docker run -p 8000:8000 -e API_CORS_ORIGINS=http://localhost:3000 bitlysis-api
```

Compose + worker PLS (RAM cao hơn, cùng volume upload):

```bash
docker compose up -d
docker compose --profile pls up -d   # thêm replica :8001 — định tuyến thủ công / LB nếu OOM PLS
```

**Lưu ý OOM PLS:** `pls-worker` là **cùng image**, target `pls-worker`; trên Render hãy tạo **Web Service thứ hai** với **nhiều RAM hơn** và cùng image/Dockerfile target `pls-worker`, trỏ client nội bộ hoặc tách route theo ADR sau.

## Biến môi trường — API (Render)

| Biến | Bắt buộc staging | Mô tả |
| --- | --- | --- |
| `APP_ENVIRONMENT` | Khuyến nghị `production` | Bật header/LLM an toàn hơn. |
| `API_CORS_ORIGINS` | **Có** | Danh sách origin (comma), khớp Vercel. |
| `API_TRUSTED_HOSTS` | Khuyến nghị khi bật | Ví dụ `bitlysis-api-staging.onrender.com,127.0.0.1,localhost` — **luôn** gồm `127.0.0.1,localhost` nếu image dùng `HEALTHCHECK` nội bộ trỏ `127.0.0.1`; Render health check qua URL công khai thì `Host` là hostname service. |
| `UPLOAD_DIR` | Container: `/data/uploads` | Ổn định với volume Render (nếu gắn disk). |
| `OPENROUTER_API_KEY` | Tùy Phase 7 | Không commit; chỉ secret dashboard. |
| `R_SUBPROCESS_TIMEOUT_SECONDS` | Tùy | Mặc định 180; PLS nặng có thể tăng. |
| `RUN_ENDPOINT_TOKEN` | Khuyến nghị | Token cho `POST /v1/run` qua header `X-Run-Token`. |
| `EXPORT_*` | Tùy | Phase 8 ZIP. |

Chi tiết đầy đủ: `services/api/.env.example`.

## Chạy R core theo lịch miễn phí (GitHub Actions)

- Endpoint server-side: `POST /v1/run`.
- Workflow có sẵn: `.github/workflows/r-core-schedule.yml`.
- Tạo 2 GitHub Actions secrets:
  - `RUN_ENDPOINT_URL`: ví dụ `https://bitlysis-api-staging.onrender.com/v1/run`
  - `RUN_ENDPOINT_TOKEN`: phải khớp env `RUN_ENDPOINT_TOKEN` trên Render
- Có thể chạy tay bằng `workflow_dispatch` hoặc để cron tự gọi mỗi ngày.

## Biến môi trường — Web (Vercel)

| Biến | Mô tả |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL API (Render). |

## Tài liệu liên quan

- `Dockerfile` — layer Python → R+CRAN → API.
- `docker-compose.yml` — local + profile `pls`.
- `apps/web/vercel.json` — header tối thiểu tầng edge.
- `docs/security-auditor-checklist.md` — Phase 12.
