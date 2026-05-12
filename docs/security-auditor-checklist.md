# Security auditor checklist — Bitlysis

Phase 12 — P0 là mục tối thiểu trước production công khai. Trạng thái ghi tại thời điểm thêm tài liệu; cần rà lại mỗi release.

## P0 (bắt buộc) — đã xử lý trong repo / vận hành

| ID | Hạng mục | Trạng thái | Bằng chứng / ghi chú |
| --- | --- | --- | --- |
| P0-01 | **Secrets không commit** (`.env`, API keys, RPC, …) | Đạt | `.gitignore` loại `.env`, `.env.*`; OpenRouter chỉ env (`app/config.py`). |
| P0-02 | **CORS** cấu hình explicit origins | Đạt | `CORSMiddleware` + `API_CORS_ORIGINS` (`app/main.py`, `app/config.py`). |
| P0-03 | **Host header** (chống host poisoning) production | Đạt (khi bật) | `TrustedHostMiddleware` khi `API_TRUSTED_HOSTS` khác rỗng (`app/main.py`). Vận hành: kèm `127.0.0.1,localhost` nếu cần health nội bộ Docker — `DEPLOY-RENDER-VERCEL.md`. |
| P0-04 | **Response headers** tối thiểu API (`nosniff`, `Referrer-Policy`; prod thêm `X-Frame-Options`, `Permissions-Policy`) | Đạt | `SecurityHeadersMiddleware` (`app/middleware/security_headers.py`). |
| P0-05 | **Rate limit** upload | Đạt | `UploadRateLimitMiddleware` (`app/middleware/upload_rate_limit.py`). |
| P0-06 | **Lỗi JSON thống nhất** + `request_id` | Đạt | `app/error_handlers.py`. |
| P0-07 | **Health** không lộ secret | Đạt | `GET /health` trả `status`/`service` (`app/main.py`). |
| P0-08 | **Tài liệu deploy** env đầy đủ | Đạt | `services/api/.env.example`, `docs/DEPLOY-RENDER-VERCEL.md`. |
| P0-09 | **Frontend edge headers** (Vercel) | Đạt | `apps/web/vercel.json`. |
| P0-10 | **PLS/R OOM** có hướng tách worker | Đạt (hướng dẫn) | `Dockerfile` target `pls-worker`, `docker-compose.yml` profile `pls`, `DEPLOY-RENDER-VERCEL.md`. |

## P1 (khuyến nghị)

- `Content-Security-Policy` cho **web** (Vercel) theo nguồn script/style thực tế.
- `Strict-Transport-Security` tại **CDN** (Vercel/Render TLS termination).
- WAF / geo restriction theo nhu cầu.
- Audit log `/v1/upload` và LLM calls (đã giới hạn log PII qua `APP_ENVIRONMENT`).

## Phân tách tầng header

| Tầng | Header / chính sách | Ghi chú |
| --- | --- | --- |
| **API (FastAPI)** | `X-Content-Type-Options`, `Referrer-Policy`, prod `X-Frame-Options`, `Permissions-Policy` | `security_headers.py` |
| **Frontend (Vercel)** | `X-Content-Type-Options`, `Referrer-Policy` | `vercel.json` |
| **CDN / TLS** | HSTS, CSP nâng cao | Cấu hình Vercel/Render dashboard |
