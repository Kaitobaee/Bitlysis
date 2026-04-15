#!/usr/bin/env Rscript
# CI / local: cài dependency bắt buộc cho runtime (Depends/Imports/LinkingTo).
# Tránh dependencies=TRUE vì sẽ kéo cả Suggests, dễ phát sinh lỗi build không cần thiết trên Render.
# Windows: ưu tiên binary + không compile từ source (tránh lỗi 'make' not found khi thiếu Rtools).
# Cảnh báo "graph / Rgraphviz are not available": gói tùy chọn (Suggests); không chặn Cronbach / EFA / PLS.

repos <- c(CRAN = "https://cloud.r-project.org")
options(repos = repos)

if (.Platform$OS.type == "windows") {
  options(pkgType = "win.binary")
  options(install.packages.compile.from.source = "never")
}

pkgs <- c("jsonlite", "psych", "seminr", "testthat")
nc <- if (.Platform$OS.type == "windows") 1L else 2L
install.packages(
  pkgs,
  repos = repos,
  dependencies = c("Depends", "Imports", "LinkingTo"),
  Ncpus = nc
)

message("OK: R deps installed (see renv.lock for pin gợi ý; CI dùng install đầy đủ dependency)")
