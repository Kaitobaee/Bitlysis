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
| `POST` | `/v1/jobs/{job_id}/hypothesis-suggestions` | **200** — gợi ý giả thuyết (Phase 7: OpenRouter + validate JSON / fallback). |
| `POST` | `/v1/jobs/{job_id}/export/start` | **202** — bắt buộc trước khi tải ZIP **nặng** (chuyển job sang `exporting`). |
| `POST` | `/v1/jobs/{job_id}/export` | **200** — tạo ZIP (matplotlib/plotly PNG, PDF bảng, docx, Excel `data_clean` + `results_raw`, `run_manifest.json`); trả file. |
| `GET` | `/v1/jobs/{job_id}/charts/matplotlib` | **200** — PNG biểu đồ matplotlib (cột số đầu tiên trong file job) để nhúng / hiển thị UI; **404** nếu không có cột số. |
| `GET` | `/v1/jobs/{job_id}/export/download` | **200** — tải lại ZIP đã build (`export_stored_as` trong meta). |
| `DELETE` | `/v1/jobs/{job_id}` | **204** — xóa file upload + meta (Phase 2 / ADR 0003). |

### Analyze — Phase 6 (chuỗi thời gian)

Body JSON với `"kind": "timeseries_forecast"`: tự detect cột ngày (thử ISO / `dayfirst` US–EU / `format=mixed`), cột giá trị số, mô hình `auto` (ETS → ARIMA), hoặc `ets` / `arima` / `prophet` (cài thêm `pip install -e ".[timeseries]"`). Kết quả trong `result_summary`: `engine: python_timeseries`, `version: 6`, `chart` (series `actual` / `fitted` / `forecast` cho frontend), `metrics` (MAPE, RMSE trên holdout), `warnings` (chuỗi ngắn, MAPE cao, …).

### Phase 7 — Gợi ý giả thuyết (OpenRouter)

`POST /v1/jobs/{job_id}/hypothesis-suggestions` — body tùy chọn `{ "force_fallback": false }`. Đọc `columns` từ meta job; gọi OpenRouter với JSON schema cố định (`app/schemas/llm.py`), validate Pydantic; timeout `LLM_TIMEOUT_SECONDS`; lỗi / timeout → **rule-based**. `source`: `openrouter` | `fallback` | `disabled_no_key`. Production: đặt `APP_ENVIRONMENT=production` và **không** bật `LLM_LOG_PROMPTS` (không log nội dung prompt/PII). Golden eval: `eval/golden/hypothesis_llm_golden.json` + `pytest tests/test_llm_golden.py`.

### Phase 8 — Visualization + export ZIP

Cấu trúc ZIP: `run_manifest.json` (merge `export` + phiên bản gói), `docs/charts/matplotlib_series.png`, `docs/charts/plotly_series.png` (nếu `export_include_plotly` và có **kaleido**: `pip install -e ".[export_viz]"`), `docs/tables/summary_tables.pdf` (ReportLab), `docs/report.docx` (python-docx; template tùy chọn `EXPORT_DOCX_TEMPLATE_PATH`), `docs/data/workbook.xlsx` (sheet **`data_clean`**, **`results_raw`**). Nếu kích thước ZIP > `EXPORT_ZIP_HEAVY_THRESHOLD_BYTES` thì phải gọi **`POST .../export/start`** khi job `succeeded` (chuyển `exporting`) rồi mới `POST .../export`. Vượt `EXPORT_MAX_ZIP_BYTES` → **413**. Kiểm thử: `pytest tests/test_export_zip_integration.py`.

### Upload tin cậy (Phase 2)

- **Magic bytes**: `.xlsx`/`.xlsm` phải bắt đầu bằng ZIP `PK`; CSV không chứa byte `\x00` trong phần đầu file — tránh đuôi giả.
- **Rate limit**: `POST /v1/upload` giới hạn theo IP (sliding window), cấu hình `UPLOAD_RATE_LIMIT_*`.
- **Retention**: nền định kỳ xóa job quá `RETENTION_HOURS` (tắt bằng `RETENTION_ENABLED=false`).

File dữ liệu và `{job_id}.meta.json` nằm trong `UPLOAD_DIR` (mặc định `./data/uploads`).

**Lỗi** (JSON): `{ "code", "message", "details", "request_id" }`.

## Biến môi trường

Xem `.env.example` (copy thành `.env`). `API_CORS_ORIGINS` là danh sách URL frontend, phân tách bằng dấu phẩy. `API_TRUSTED_HOSTS` (tùy chọn): bật `TrustedHostMiddleware` khi production; nên gồm `127.0.0.1,localhost` nếu dùng `HEALTHCHECK` Docker nội bộ.

## Docker & triển khai (Phase 11)

Xây từ **root monorepo** (cần `packages/r-pipeline`):

```bash
cd ../..   # repo root
docker build -t bitlysis-api .
```

Blueprint Render, Vercel, cold start: [`docs/DEPLOY-RENDER-VERCEL.md`](../../docs/DEPLOY-RENDER-VERCEL.md). Checklist bảo mật: [`docs/security-auditor-checklist.md`](../../docs/security-auditor-checklist.md). Methodology user-facing: [`docs/Methodology.md`](../../docs/Methodology.md).
