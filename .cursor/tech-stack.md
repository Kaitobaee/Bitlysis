# Tech stack (Bitlysis)

Cập nhật file này khi đổi phiên bản công cụ. Agent đọc path: `.cursor/tech-stack.md`.

## Archetype (chọn một hoặc liệt kê chính + phụ)

Ghi rõ để rule/persona đúng: **Consumer Web2** | **Consumer Web3** | **DeFi** | **Data analysis** | **AI agent** | **Infra / dev tool** | **Browser extension** | **Game (web)** | **Fullstack (general)** — xem `AGENT.md` §18.

**Primary archetype:** Data analysis

**Secondary (nếu có):** AI agent, Consumer Web2 (fullstack SaaS)

## Core (điền theo dự án)

| Layer | Choice | Version / ghi chú |
| --- | --- | --- |
| Runtime / app | Node.js | ≥ 22 (xem `package.json` engines) |
| Frontend | Next.js + React + Tailwind | Next 15.2.x, React 19, Tailwind 4 |
| Backend | FastAPI (Python) | ≥ 3.11; uvicorn |
| Package manager | pnpm (JS) / pip (Python) | pnpm 9.x; Python venv trong `services/api` |

## R (phân tích dữ liệu)

| Item | Value |
| --- | --- |
| R version | 4.4.x (khuyến nghị) |
| Reproducibility | `renv` (khuyến nghị) |
| Báo cáo | Quarto / R Markdown |
| Lint / style | `lintr`, `styler` |
| Đọc SPSS / Stata | `haven` (`.sav`, `.dta`) + ghi chú missing codes |

## C++ (hiệu năng)

| Item | Value |
| --- | --- |
| Standard | _C++17 / C++20 / C++23_ |
| Build | CMake (phiên bản tối thiểu) |
| Compiler | MSVC / GCC / Clang |
| Tests | Catch2 / GoogleTest _(chọn một, ghi rõ)_ |
| Sanitizer / ASan | _bật khi debug nếu có_ |

## Web3 (nếu có)

| Item | Value |
| --- | --- |
| Chain / RPC | _dùng env, không hardcode_ |
| Contract tooling | Foundry / Hardhat |

## Lệnh quality gates (điền sát repo)

```text
pnpm install && pnpm lint:web && pnpm build:web
cd services/api && pip install -e ".[dev]" && ruff check app tests scripts && pytest tests -q
# Phase 6 timeseries: tests/test_timeseries_engine.py + fixtures/timeseries_eu.csv
# Phase 7 LLM: eval/golden/hypothesis_llm_golden.json + tests/test_llm_golden.py, test_hypothesis_router.py
# Phase 8 export: tests/test_export_zip_integration.py (ZIP + openpyxl sheet count)
# Phase 9 frontend: apps/web — upload/poll/analyze, messages/vi.json + en.json, sonner toasts; E2E tay: apps/web/README.md
# Phase 10 WASM: packages/asm-wasm (AssemblyScript) → public/wasm/preview_core.wasm; worker file-preview; wasm-bundle-sizes.json
# Phase 11 infra: Dockerfile (layers R/Python), docker-compose profile pls, render.yaml, docs/DEPLOY-RENDER-VERCEL.md
# Phase 12: docs/security-auditor-checklist.md, docs/Methodology.md, SecurityHeadersMiddleware, apps/web/vercel.json
# CI: .github/workflows/ci.yml (push/PR main|master)
# R (Phase 5): cd packages/r-pipeline && Rscript tools/ci_install.R && Rscript -e "testthat::test_dir('tests/testthat')"
```
