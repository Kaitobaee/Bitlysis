# Bitlysis API

FastAPI orchestrator: upload, analyze (Python + optional R subprocess), export.

## Chạy local

```bash
cd services/api
python -m venv .venv
# Windows: .venv\Scripts\activate  rồi pip install …
# Hoặc (Windows): py -3 -m pip install -e ".[dev]"
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

### API v1 (Phase 1)

Tất cả endpoint dưới prefix **`/v1`**. Header **`X-Request-Id`** được set trên mọi response (và có thể gửi lên để trace).

| Method | Path | Mô tả |
| --- | --- | --- |
| `POST` | `/v1/upload` | `multipart/form-data` field `file` (`.csv`, `.xlsx`, `.xlsm`). Trả `job_id`, `status` (`uploaded`), cột, preview… |
| `GET` | `/v1/jobs/{job_id}` | Trạng thái job + meta (filename, cột, `error`, `result_summary`…) |
| `POST` | `/v1/jobs/{job_id}/analyze` | **202** — chấp nhận chạy phân tích nền (stub Phase 1 → `succeeded`). Poll `GET` cho đến `succeeded` / `failed`. |
| `DELETE` | `/v1/jobs/{job_id}` | **204** — xóa file upload + meta (Phase 2 / ADR 0003). |

### Upload tin cậy (Phase 2)

- **Magic bytes**: `.xlsx`/`.xlsm` phải bắt đầu bằng ZIP `PK`; CSV không chứa byte `\x00` trong phần đầu file — tránh đuôi giả.
- **Rate limit**: `POST /v1/upload` giới hạn theo IP (sliding window), cấu hình `UPLOAD_RATE_LIMIT_*`.
- **Retention**: nền định kỳ xóa job quá `RETENTION_HOURS` (tắt bằng `RETENTION_ENABLED=false`).

File dữ liệu và `{job_id}.meta.json` nằm trong `UPLOAD_DIR` (mặc định `./data/uploads`).

**Lỗi** (JSON): `{ "code", "message", "details", "request_id" }`.

## Biến môi trường

Xem `.env.example` (copy thành `.env`). `API_CORS_ORIGINS` là danh sách URL frontend, phân tách bằng dấu phẩy.
