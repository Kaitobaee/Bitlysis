test_that("Cronbach chạy với 3 item", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  r <- bitlysis_run_cronbach(df, list(type = "cronbach_alpha", scale_id = "s", items = c("x1", "x2", "x3")))
  expect_true(r$ok)
  expect_true(r$ran)
  expect_false(r$skipped)
  expect_true(r$raw_alpha > 0 && r$raw_alpha < 1)
})

test_that("Cronbach skip khi <2 item", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  r <- bitlysis_run_cronbach(df, list(type = "cronbach_alpha", scale_id = "s", items = c("x1")))
  expect_true(r$skipped)
})

test_that("EFA chạy với 5 biến", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  r <- bitlysis_run_efa(df, list(type = "efa", variables = c("x1", "x2", "x3", "x4", "x5"), n_factors = 2L))
  expect_true(r$ok)
  expect_true(r$ran)
  expect_false(r$skipped)
})

test_that("EFA skip khi ít biến", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  r <- bitlysis_run_efa(df, list(type = "efa", variables = c("x1", "x2"), n_factors = 1L))
  expect_true(r$skipped)
})

test_that("PLS skip khi n < min_n (gate)", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  df <- df[1:20, , drop = FALSE]
  blk <- list(
    type = "pls_sem",
    min_n = 100L,
    min_items_per_construct = 2L,
    min_constructs = 2L,
    constructs = list(
      list(name = "ETA", mode = "reflective", indicators = c("x1", "x2", "x3")),
      list(name = "KSI", mode = "reflective", indicators = c("y1", "y2", "y3"))
    ),
    paths = list(list(from = "KSI", to = "ETA"))
  )
  r <- bitlysis_run_pls(df, blk)
  expect_true(r$skipped)
  expect_true(length(r$warnings) >= 1L)
})

test_that("PLS chạy khi đủ n và gate (reflective)", {
  df <- read.csv(testthat::test_path("fixtures", "tiny_pls.csv"), stringsAsFactors = FALSE)
  blk <- list(
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
  r <- bitlysis_run_pls(df, blk)
  expect_true(r$ok)
  expect_false(r$skipped)
  expect_true(isTRUE(r$ran))
})
