# Stub: xác nhận R chạy được trong CI/local trước khi gắn thư viện phân tích.
msg <- list(
  ok = TRUE,
  package = "bitlysis-r-pipeline",
  note = "Replace with real pipeline I/O (JSON) when API integrates."
)
if (requireNamespace("jsonlite", quietly = TRUE)) {
  cat(jsonlite::toJSON(msg, auto_unbox = TRUE), "\n")
} else {
  cat('{"ok":true,"note":"install jsonlite for JSON output"}\n')
}
