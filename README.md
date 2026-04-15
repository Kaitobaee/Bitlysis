# Bitlysis

Bitlysis là nền tảng phân tích dữ liệu và nội dung theo mô hình web + API + pipeline thống kê. Dự án hiện tập trung vào 4 hướng chính:

1. Phân tích website.
2. Phân tích file Excel, Word và file dữ liệu.
3. Phân tích nội dung văn bản, gợi ý bài báo liên quan và tóm tắt từng bài.
4. Phân tích dữ liệu thống kê có cấu trúc, xuất báo cáo và minh bạch backend.

## Cấu trúc repo

- `apps/web` - Next.js frontend.
- `services/api` - FastAPI orchestrator, job API, web analysis API.
- `packages/r-pipeline` - R scripts và `renv` cho các phân tích nâng cao.
- `docs` - tài liệu kiến trúc, ADR và báo cáo đối chiếu.

## Yêu cầu môi trường

- Node.js 22+
- pnpm 9.x
- Python 3.11+
- R 4.4+ nếu chạy pipeline R

## Chạy frontend

```bash
pnpm install
pnpm dev:web
```

Frontend mặc định chạy tại `http://localhost:3000`.

## Chạy API

```bash
cd services/api
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API mặc định chạy tại `http://localhost:8000`.

## Biến môi trường

Copy `services/api/.env.example` sang `services/api/.env` rồi cấu hình:

- `API_CORS_ORIGINS`
- `UPLOAD_DIR`
- `LLM_ENABLED`
- `OPENROUTER_API_KEY` hoặc `OPENAI_API_KEY`
- `OPENROUTER_MODEL` hoặc `OPENAI_MODEL`

## Lệnh kiểm tra nhanh

Frontend:

```bash
pnpm lint:web
pnpm build:web
```

API:

```bash
cd services/api
ruff check app tests scripts
pytest tests -q
```

## Tài liệu liên quan

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/adr/](docs/adr/)
- [docs/bao-cao-doi-chieu-de-tai-va-san-pham.md](docs/bao-cao-doi-chieu-de-tai-va-san-pham.md)

## Ghi chú

- Phần AI web analysis hiện hỗ trợ phân tích website, nội dung text và gợi ý bài báo liên quan.
- Phần data analysis ưu tiên output có cấu trúc, provenance và khả năng kiểm chứng.