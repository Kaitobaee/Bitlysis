pkg_root <- normalizePath(testthat::test_path("..", ".."), winslash = "/")
Sys.setenv(BITLYSIS_R_PKG_ROOT = pkg_root)
r_files <- list.files(file.path(pkg_root, "R"), pattern = "\\.[Rr]$", full.names = TRUE)
for (f in r_files) {
  source(f, encoding = "UTF-8")
}
suppressPackageStartupMessages({
  library(jsonlite)
  library(psych)
  library(seminr)
})
