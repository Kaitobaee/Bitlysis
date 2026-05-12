# ADR 0005 — Python-only statistical engine

Date: 2026-05-11
Status: Accepted

## Context

ADR 0001 chốt monorepo có `packages/r-pipeline` (R + `renv`) cho các phân tích
nâng cao (Cronbach α, EFA, PLS-SEM), gọi qua `Rscript` subprocess từ FastAPI.

Trong quá trình triển khai, layer R + CRAN gây các vấn đề:

- Deploy Docker chậm (~50–90s cold start trên Render) do `Rscript ci_install.R`
  cài nhiều dependency native (`seminr`, `psych`, `jsonlite` …).
- CI cần job riêng `r-pipeline` cache `R_LIBS_USER`.
- `renv.lock` phụ thuộc nguồn CRAN nội bộ; vài lần build fail không liên quan
  source code.
- Worker PLS phải tạo service Docker thứ hai trên Render với RAM cao hơn.
- Phụ thuộc kép Python ↔ R làm pipeline khó debug và testable.

## Decision

Bỏ runtime R; port Cronbach α, EFA, PLS-SEM sang **thuần Python/numpy/scipy**:

- `services/api/app/services/psychometrics/cronbach.py` — alpha thường +
  standardized + item-total stats.
- `services/api/app/services/psychometrics/efa.py` — PAF + varimax (custom
  implementation, không phụ thuộc `factor_analyzer` để tránh sklearn breakage).
  KMO/Bartlett tự tính từ correlation matrix.
- `services/api/app/services/psychometrics/pls_sem.py` — NIPALS reflective
  (Mode A) + bootstrap CI + HTMT + Fornell-Larcker + AVE + CR + rho_A + Q²
  (blindfolding) + f² (feature-complete so với seminr trên phạm vi reflective).

`services/api/app/services/r_pipeline.py` giữ làm **shim** chuyển tiếp gọi
sang `run_psychometrics` để backward compat (test cũ + endpoint `/v1/run`).

Schema discriminator chấp nhận cả `kind: "psychometrics"` và `kind: "r_pipeline"`.

## Consequences

**Positive:**

- Docker image 1 stage (Python 3.11 slim), cold start nhanh hơn ~2×.
- CI job `r-pipeline` được xóa; không cần cache `R_LIBS_USER`.
- Test parity chạy local mà không cần `Rscript`.
- Thay `renv.lock` bằng `pip_lock_sha256` (hash `pyproject.toml`) trong provenance.
- Bỏ `R_SUBPROCESS_TIMEOUT_SECONDS`, `pls-worker` profile trong compose.

**Negative / trade-off:**

- Output PLS-SEM không trùng tuyệt đối với `seminr` (tham chiếu R) — tolerance
  ±0.02 cho path_coef/R²/AVE, ±0.05 cho HTMT, bootstrap CI overlap. Đã được
  ghi nhận trong test parity.
- Bộ phụ thuộc psychometrics nằm trong codebase Bitlysis → phải tự maintain
  (không dựa vào team `seminr`).
- `factor_analyzer` ban đầu được cài rồi gỡ vì incompat sklearn 1.8+; thay bằng
  implementation custom PAF/varimax — giảm rủi ro nhưng cần kiểm tra parity.

## Alternatives considered

- Giữ R + pin Docker base image cũ → vẫn chậm cold start, không giải quyết
  fundamental issue.
- Dùng `plspm` PyPI package → kém maintain, output không feature-complete (thiếu
  HTMT/Q²/f²).
- Triển khai PLS-SEM bằng `semopy` → `semopy` là CB-SEM, không phải PLS-SEM.

## Migration

- Endpoint `kind: "r_pipeline"` vẫn hoạt động (alias `PsychometricsSpec`).
- Field response `r_returncode`, `r_output` được giữ trong PsychometricsSpec
  branch của `core/analysis.py` để client cũ không gãy.
- Workflow `r-core-schedule.yml` đổi nội dung gọi engine Python; tên file giữ
  để CI subscribers không bị mất reference.

## Related

- ADR 0001 — Monorepo architecture (R pipeline)
- `docs/Methodology.md` — mapping đề tài ↔ endpoint
- `services/api/tests/test_psychometrics.py` — parity tests
