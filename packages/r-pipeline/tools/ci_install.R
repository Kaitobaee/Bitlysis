#!/usr/bin/env Rscript
# CI / local: mặc định cài dependency runtime tối thiểu cho production image.
# Tránh dependencies=TRUE vì sẽ kéo cả Suggests, dễ phát sinh lỗi build không cần thiết trên Render.
# Dev/test dependency (testthat) chỉ cài khi BITLYSIS_R_INSTALL_DEV=true.
# Windows: ưu tiên binary + không compile từ source (tránh lỗi 'make' not found khi thiếu Rtools).
# Cảnh báo "graph / Rgraphviz are not available": gói tùy chọn (Suggests); không chặn Cronbach / EFA / PLS.

repos <- c(CRAN = "https://cloud.r-project.org")
options(repos = repos)

if (.Platform$OS.type == "windows") {
  options(pkgType = "win.binary")
  options(install.packages.compile.from.source = "never")
}

pkgs <- c("jsonlite", "psych", "seminr")
install_dev <- tolower(Sys.getenv("BITLYSIS_R_INSTALL_DEV", "false")) %in% c("1", "true", "yes")
if (install_dev) {
  pkgs <- c(pkgs, "testthat")
}
nc <- if (.Platform$OS.type == "windows") 1L else 2L
install.packages(
  pkgs,
  repos = repos,
  dependencies = c("Depends", "Imports", "LinkingTo"),
  Ncpus = nc
)

message(sprintf("OK: R deps installed (%s mode)", if (install_dev) "dev" else "runtime"))
