#!/usr/bin/env Rscript
# JSON request path = argv[1]. JSON stdout. Log to stderr.
# Đặt BITLYSIS_R_PKG_ROOT = thư mục packages/r-pipeline (Python set sẵn).

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1L) {
  message("Usage: Rscript run_analysis.R <request.json>")
  cat("{\"ok\":false,\"error\":\"missing request json path\"}\n")
  quit(status = 1L)
}

req_path <- args[[1L]]
pkg_root <- Sys.getenv("BITLYSIS_R_PKG_ROOT", unset = getwd())
r_dir <- file.path(pkg_root, "R")
r_files <- list.files(r_dir, pattern = "\\.[Rr]$", full.names = TRUE)
if (length(r_files) < 1L) {
  cat("{\"ok\":false,\"error\":\"No R sources — set BITLYSIS_R_PKG_ROOT\"}\n")
  quit(status = 1L)
}
suppressPackageStartupMessages(library(jsonlite))
for (f in r_files) {
  source(f, encoding = "UTF-8")
}

run_one <- function(df, blk) {
  typ <- blk$type
  if (is.null(typ)) {
    return(list(
      type = "unknown",
      ok = FALSE,
      skipped = TRUE,
      warnings = list("Thiếu trường type trong analysis block.")
    ))
  }
  switch(
    typ,
    cronbach_alpha = bitlysis_run_cronbach(df, blk),
    efa = bitlysis_run_efa(df, blk),
    pls_sem = bitlysis_run_pls(df, blk),
    list(
      type = typ,
      ok = FALSE,
      skipped = TRUE,
      warnings = list(paste("Unknown analysis type:", typ))
    )
  )
}

out <- tryCatch(
  {
    req <- bitlysis_read_request(req_path)
    csv_path <- req$csv_path
    if (is.null(csv_path) || !nzchar(csv_path)) {
      stop("Thiếu csv_path trong request JSON")
    }
    if (!file.exists(csv_path)) {
      stop(paste("Không tìm thấy file:", csv_path))
    }
    df <- bitlysis_read_csv(csv_path)
    blocks <- req$analyses
    if (is.null(blocks) || length(blocks) < 1L) {
      stop("Thiếu analyses[]")
    }
    res <- lapply(blocks, function(b) run_one(df, b))
    list(
      version = jsonlite::unbox(1L),
      ok = jsonlite::unbox(TRUE),
      engine = jsonlite::unbox("bitlysis_r_pipeline"),
      results = res
    )
  },
  error = function(e) {
    list(
      version = jsonlite::unbox(1L),
      ok = jsonlite::unbox(FALSE),
      engine = jsonlite::unbox("bitlysis_r_pipeline"),
      error = conditionMessage(e),
      results = list()
    )
  }
)

cat(jsonlite::toJSON(out, auto_unbox = TRUE, null = "null", dataframe = "rows"), "\n", sep = "")
quit(status = if (isTRUE(out$ok)) 0L else 1L)
