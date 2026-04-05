#!/usr/bin/env Rscript
# Maintainer: sau khi ci_install.R, chạy trong packages/r-pipeline để tạo renv.lock đầy đủ.
repos <- c(CRAN = "https://cloud.r-project.org")
if (!requireNamespace("renv", quietly = TRUE)) {
  install.packages("renv", repos = repos)
}
renv::init(project = ".", bare = TRUE, force = TRUE)
renv::install(
  c("jsonlite", "psych", "seminr", "testthat"),
  prompt = FALSE,
)
renv::snapshot(prompt = FALSE)
message("Đã cập nhật renv.lock — kiểm tra diff trước khi commit.")
