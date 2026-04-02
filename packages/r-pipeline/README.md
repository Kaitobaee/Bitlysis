# R pipeline (Bitlysis)

Phân tích thống kê nâng cao (Cronbach, EFA, PLS-SEM, …) chạy headless, được **FastAPI** gọi qua `Rscript`.

## Thiết lập `renv` (một lần)

Cài [R](https://cran.r-project.org/) ≥ 4.4, trong thư mục này:

```r
install.packages("renv")
renv::init()
```

Sau đó thêm package cần thiết (ví dụ `jsonlite`, `psych`, …) và `renv::snapshot()`.

## Chạy thử script mẫu

```bash
Rscript R/pipeline_stub.R
```

Output JSON tối thiểu để kiểm tra môi trường.

## Quy ước

- Input/Output: JSON qua stdin/stdout hoặc file path (sẽ thống nhất khi nối API).
- Không `setwd()` tuyệt đối — dùng path tương đối repo hoặc tham số CLI.
