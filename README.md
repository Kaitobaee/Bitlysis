# Bitlysis

Bitlysis là **statistical copilot** trên đám mây cho sinh viên, giảng viên và người làm khảo sát. Người dùng tải file, hệ thống tự động profile → làm sạch → chọn phương pháp → kiểm định → xuất báo cáo có cấu trúc và minh bạch.

## Lõi sản phẩm (đề tài)

1. **Phân tích thống kê tự động** trên file CSV/Excel: t-test, ANOVA, hồi quy OLS, chi-square, chuỗi thời gian (ETS/ARIMA/Prophet).
2. **Psychometrics Python**: Cronbach α, EFA, PLS-SEM (bootstrap, HTMT, Q², f²) — không còn phụ thuộc R, deploy Python-only.
3. **AI hỗ trợ** (rule-based mặc định, LLM tuỳ chọn) gợi ý giả thuyết; engine thống kê vẫn quyết định kết quả.
4. **Minh bạch học thuật**: hash file gốc, hash lock dependencies, random seed, version package, decision trace, manifest JSON.
5. **Xuất ZIP** gồm Word học thuật, Excel (data_raw + data_clean + cleaning_log + results_raw), PDF bảng, biểu đồ PNG.

## Module phụ trợ

- **Phân tích website / nội dung**: tab riêng (`/web/analyze`), giúp demo nhanh; không thay thế phân tích thống kê.

## Cấu trúc repo

- `apps/web` — Next.js frontend (`ResultSummary` academic-first).
- `services/api` — FastAPI orchestrator + engine Python (`stats_engine`, `psychometrics`, `timeseries_engine`).
- `packages/r-pipeline` — **legacy**, chỉ giữ fixture/test tham chiếu; runtime không còn gọi R.
- `docs` — kiến trúc, ADR, báo cáo đối chiếu, methodology.

## Yêu cầu môi trường

- Node.js 22+
- pnpm 9.x
- **Python 3.11+** (bắt buộc; pin trong `pyproject.toml`)
- ~~R 4.4+~~ — **không còn cần** kể từ ADR 0005.

## Chạy frontend

```bash
pnpm install
pnpm dev:web
```

Frontend mặc định chạy tại `http://localhost:3000`.

## Chạy API

```bash
cd services/api
py -3.11 -m venv .venv
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
- `OPENROUTER_API_KEY` hoặc `OPENAI_API_KEY` (tuỳ chọn — chỉ dùng cho gợi ý giả thuyết, không thay engine)

## Quy trình một-lần-chạy (`comprehensive_analysis`)

`POST /v1/upload` → `POST /v1/jobs/{id}/analyze` với spec `{ "kind": "comprehensive_analysis", ... }` →
orchestrator tự chạy profiling → cleaning → hypothesis suggest → engine dispatch → unified schema.
Xem chi tiết: [docs/Methodology.md](docs/Methodology.md).

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
- [docs/adr/](docs/adr/) (ADR 0005: Python-only stats engine)
- [docs/Methodology.md](docs/Methodology.md)
- [docs/bao-cao-doi-chieu-de-tai-va-san-pham.md](docs/bao-cao-doi-chieu-de-tai-va-san-pham.md)
