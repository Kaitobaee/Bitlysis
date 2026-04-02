# Đóng góp Bitlysis

## Yêu cầu môi trường

- **Node** ≥ 22, **pnpm** 9.x
- **Python** ≥ 3.11 (CI dùng 3.12)
- Tuân thủ [.cursor/.agents/AGENT.md](.cursor/.agents/AGENT.md) và [.cursor/tech-stack.md](.cursor/tech-stack.md)

## Lệnh local (quality gates)

Từ **root repo**:

```bash
pnpm install
pnpm lint:web
pnpm build:web
```

API:

```bash
cd services/api
pip install -e ".[dev]"
ruff check app tests
pytest tests -q
```

Chạy API dev:

```bash
cd services/api
uvicorn app.main:app --reload --port 8000
```

## CI

Push/PR lên `main` hoặc `master` chạy [.github/workflows/ci.yml](.github/workflows/ci.yml): **ruff + pytest** (`services/api`), **lint + build** (`apps/web`).

## Dữ liệu thử

File mẫu **tổng hợp, không PII** nằm trong [services/api/tests/fixtures](services/api/tests/fixtures) — xem README trong thư mục đó.

## ADR

Quyết định kiến trúc: [docs/adr/](docs/adr/).
