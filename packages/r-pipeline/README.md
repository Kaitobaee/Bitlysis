# R pipeline (Bitlysis) — Phase 5

Phân tích **Cronbach α**, **EFA** (psych::fa), **PLS-SEM** (seminr) qua **CLI JSON**, được FastAPI gọi bằng `Rscript` (timeout + stderr).

## Cấu trúc

| Thành phần | Mô tả |
|------------|--------|
| `R/bitlysis_run.R` | Logic + **gate PLS** (min_n, min_items_per_construct, min_constructs) — không crash, trả `skipped` + `warnings`. |
| `inst/cli/run_analysis.R` | Đọc JSON request (path argv), đọc CSV, ghi JSON stdout. |
| `tests/testthat/` | `testthat` + fixture `fixtures/tiny_pls.csv` + integration gọi CLI. |
| `renv.lock` | Pin gợi ý; CI cài **`dependencies=TRUE`** qua `tools/ci_install.R` (đủ phụ thuộc seminr). |

## Request JSON (stdin file path truyền cho Rscript)

```json
{
  "version": 1,
  "csv_path": "/abs/path/to/data.csv",
  "analyses": [
    { "type": "cronbach_alpha", "scale_id": "trust", "items": ["x1","x2","x3"] },
    { "type": "efa", "variables": ["x1","x2","x3","x4","x5"], "n_factors": 2, "min_n": 10 },
    {
      "type": "pls_sem",
      "min_n": 100,
      "min_items_per_construct": 2,
      "min_constructs": 2,
      "constructs": [
        { "name": "ETA", "mode": "reflective", "indicators": ["x1","x2","x3"] },
        { "name": "KSI", "mode": "reflective", "indicators": ["y1","y2","y3"] }
      ],
      "paths": [ { "from": "KSI", "to": "ETA" } ]
    }
  ]
}
```

## Chạy local

```bash
cd packages/r-pipeline
Rscript tools/ci_install.R
Rscript -e "testthat::test_dir('tests/testthat')"
```

CLI (đặt `BITLYSIS_R_PKG_ROOT` = thư mục `packages/r-pipeline`):

```bash
export BITLYSIS_R_PKG_ROOT=$PWD
printf '%s' '{"version":1,"csv_path":"tests/testthat/fixtures/tiny_pls.csv","analyses":[{"type":"cronbach_alpha","scale_id":"t","items":["x1","x2","x3"]}]}' > /tmp/req.json
Rscript inst/cli/run_analysis.R /tmp/req.json
```

**Windows — Command Prompt (cmd):** không dùng cú pháp PowerShell (`$env:...`).

```bat
cd C:\path\to\Bitlysis\packages\r-pipeline
set "BITLYSIS_R_PKG_ROOT=%CD%"
Rscript inst\cli\run_analysis.R C:\path\to\req.json
```

**Windows — PowerShell:**

```powershell
cd C:\path\to\Bitlysis\packages\r-pipeline
$env:BITLYSIS_R_PKG_ROOT = (Get-Location).Path
Rscript inst\cli\run_analysis.R C:\path\to\req.json
```

## API (Python)

`POST /v1/jobs/{id}/analyze` với body:

```json
{
  "kind": "r_pipeline",
  "analyses": [ ... như trên (không cần csv_path — API tự xuất CSV từ job) ... ]
}
```

## `renv.lock` đầy đủ

```bash
cd packages/r-pipeline
Rscript tools/bootstrap_renv.R
```

## Stub cũ

`R/pipeline_stub.R` chỉ để smoke-test môi trường; luồng chính dùng `inst/cli/run_analysis.R`.
