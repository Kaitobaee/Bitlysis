test_that("CLI JSON in/out với fixture (integration)", {
  skip_on_cran()
  csv <- normalizePath(testthat::test_path("fixtures", "tiny_pls.csv"), winslash = "/")
  req <- list(
    version = 1L,
    csv_path = csv,
    analyses = list(
      list(type = "cronbach_alpha", scale_id = "t", items = c("x1", "x2", "x3")),
      list(
        type = "pls_sem",
        min_n = 30L,
        min_items_per_construct = 2L,
        min_constructs = 2L,
        constructs = list(
          list(name = "ETA", mode = "reflective", indicators = c("x1", "x2", "x3")),
          list(name = "KSI", mode = "reflective", indicators = c("y1", "y2", "y3"))
        ),
        paths = list(list(from = "KSI", to = "ETA"))
      )
    )
  )
  tf <- tempfile(fileext = ".json")
  jsonlite::write_json(req, tf, auto_unbox = TRUE)
  cli <- file.path(pkg_root, "inst", "cli", "run_analysis.R")
  skip_if_not(file.exists(cli), "CLI script missing")
  rx <- Sys.which("Rscript")
  skip_if(rx == "", "Rscript not on PATH")
  Sys.setenv(BITLYSIS_R_PKG_ROOT = pkg_root)
  on.exit(Sys.unsetenv("BITLYSIS_R_PKG_ROOT"), add = TRUE)
  out <- suppressWarnings(system2(rx, args = c(cli, tf), stdout = TRUE, stderr = TRUE))
  expect_true(length(out) >= 1L)
  js <- jsonlite::fromJSON(paste(out, collapse = ""))
  expect_true(js$ok)
  expect_length(js$results, 2L)
  expect_equal(js$results[[1]]$type, "cronbach_alpha")
  expect_equal(js$results[[2]]$type, "pls_sem")
})
