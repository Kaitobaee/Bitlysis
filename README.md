# Bitlysis

Công cụ phân tích dữ liệu cloud-based (StatOne). Monorepo:

| Thư mục | Vai trò |
| --- | --- |
| [`apps/web`](apps/web) | Next.js 15 (frontend, Vercel) |
| [`services/api`](services/api) | FastAPI orchestrator (Docker / Render) |
| [`packages/r-pipeline`](packages/r-pipeline) | R scripts + `renv` (phân tích nâng cao) |

**Đóng góp & CI:** [CONTRIBUTING.md](CONTRIBUTING.md) — GitHub Actions chạy ruff/pytest (API) và lint/build (web).

Kiến trúc & quyết định: [docs/adr/](docs/adr/) (ADR 0001–0004).

## Yêu cầu

- **Node** ≥ 22, **pnpm** 9.x  
- **Python** ≥ 3.11  
- **R** ≥ 4.4 (khi chạy pipeline R)

## Frontend

```bash
pnpm install
pnpm dev:web
```

Mặc định: <http://localhost:3000>.

## API

```bash
cd services/api
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Mặc định: <http://localhost:8000/docs>.

Sao chép `services/api/.env.example` → `services/api/.env` và chỉnh `API_CORS_ORIGINS` nếu cần.

## R pipeline

Xem [packages/r-pipeline/README.md](packages/r-pipeline/README.md).

## Chuẩn dự án Cursor

- [`.cursor/.agents/AGENT.md`](.cursor/.agents/AGENT.md)
- [`.cursor/tech-stack.md`](.cursor/tech-stack.md)
- [`.cursor/.docs/docs.md`](.cursor/.docs/docs.md)
