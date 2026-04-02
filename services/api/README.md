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

### Upload

`POST /upload` — form field `file` (`.csv`, `.xlsx`, `.xlsm`). Trả về `job_id`, `columns`, `row_preview_count` (số dòng đọc để xác thực), `stored_path`. File và `{job_id}.meta.json` nằm trong `UPLOAD_DIR` (mặc định `./data/uploads`).

## Biến môi trường

Xem `.env.example` (copy thành `.env`). `API_CORS_ORIGINS` là danh sách URL frontend, phân tách bằng dấu phẩy.
