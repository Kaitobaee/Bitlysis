# Core runners: Cronbach, EFA, PLS-SEM (gates). Used by inst/cli/run_analysis.R

`%||%` <- function(x, y) if (is.null(x)) y else x

bitlysis_read_request <- function(path) {
  raw <- readBin(path, "raw", file.info(path)$size)
  txt <- rawToChar(raw)
  Encoding(txt) <- "UTF-8"
  jsonlite::fromJSON(txt, simplifyVector = TRUE, simplifyDataFrame = FALSE)
}

bitlysis_read_csv <- function(csv_path) {
  utils::read.csv(
    csv_path,
    stringsAsFactors = FALSE,
    fileEncoding = "UTF-8",
    check.names = FALSE,
    na.strings = c("", "NA", "NaN"),
  )
}

bitlysis_run_cronbach <- function(df, block) {
  items <- unlist(block$items)
  sid <- block$scale_id %||% "scale"
  w <- character()
  if (length(items) < 2L) {
    return(list(
      type = "cronbach_alpha",
      scale_id = sid,
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list("Cần ít nhất 2 biến cho Cronbach alpha."),
      gates = list(min_items = 2L, n_items = length(items))
    ))
  }
  miss <- setdiff(items, names(df))
  if (length(miss) > 0) {
    return(list(
      type = "cronbach_alpha",
      scale_id = sid,
      ok = FALSE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(paste("Thiếu cột:", paste(miss, collapse = ", "))),
      gates = list()
    ))
  }
  sub <- df[, items, drop = FALSE]
  sub[] <- lapply(sub, function(x) if (is.numeric(x)) x else suppressWarnings(as.numeric(x)))
  cc <- stats::complete.cases(sub)
  n_ok <- sum(cc)
  if (n_ok < 2L) {
    return(list(
      type = "cronbach_alpha",
      scale_id = sid,
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list("Không đủ quan sát hoàn chỉnh sau khi ép numeric."),
      gates = list(n_complete = n_ok)
    ))
  }
  a <- psych::alpha(sub[cc, , drop = FALSE], check.keys = FALSE)
  list(
    type = "cronbach_alpha",
    scale_id = sid,
    ok = TRUE,
    ran = TRUE,
    skipped = FALSE,
    raw_alpha = unname(a$total$raw_alpha),
    std_alpha = unname(a$total$std.alpha),
    n = n_ok,
    warnings = if (length(w)) as.list(w) else list(),
    gates = list(min_items = 2L)
  )
}

bitlysis_run_efa <- function(df, block) {
  vars <- unlist(block$variables)
  k <- as.integer(block$n_factors %||% 2L)
  min_vars <- as.integer(block$min_variables %||% 3L)
  min_n <- as.integer(block$min_n %||% 10L)
  w <- character()
  if (length(vars) < min_vars) {
    return(list(
      type = "efa",
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(sprintf("EFA skipped: %d biến < min_variables=%d", length(vars), min_vars)),
      gates = list(n_vars = length(vars), min_variables = min_vars)
    ))
  }
  miss <- setdiff(vars, names(df))
  if (length(miss) > 0) {
    return(list(
      type = "efa",
      ok = FALSE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(paste("Thiếu cột:", paste(miss, collapse = ", "))),
      gates = list()
    ))
  }
  sub <- df[, vars, drop = FALSE]
  sub[] <- lapply(sub, function(x) if (is.numeric(x)) x else suppressWarnings(as.numeric(x)))
  cc <- stats::complete.cases(sub)
  n_ok <- sum(cc)
  if (n_ok < min_n) {
    return(list(
      type = "efa",
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(sprintf("EFA skipped: n=%d < min_n=%d", n_ok, min_n)),
      gates = list(n = n_ok, min_n = min_n)
    ))
  }
  R <- stats::cor(sub[cc, , drop = FALSE], use = "pairwise.complete.obs")
  fit <- tryCatch(
    psych::fa(
      r = R,
      nfactors = k,
      n.obs = n_ok,
      rotate = "varimax",
      fm = "minres"
    ),
    error = function(e) list(error = conditionMessage(e))
  )
  if (!is.null(fit$error)) {
    return(list(
      type = "efa",
      ok = FALSE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(fit$error),
      gates = list()
    ))
  }
  load <- unclass(fit$loadings)
  vp <- tryCatch(
    as.numeric(fit$Vaccounted[2, seq_len(k)]),
    error = function(e) rep(NA_real_, k)
  )
  load_df <- as.data.frame(as.matrix(load[, seq_len(k), drop = FALSE]))
  names(load_df) <- paste0("F", seq_len(k))
  load_df$item <- rownames(load_df)
  list(
    type = "efa",
    ok = TRUE,
    ran = TRUE,
    skipped = FALSE,
    n_factors = k,
    n = n_ok,
    variance_proportion = vp,
    loadings = load_df,
    warnings = if (length(w)) as.list(w) else list(),
    gates = list(min_variables = min_vars, min_n = min_n)
  )
}

bitlysis_run_pls <- function(df, block) {
  min_n <- as.integer(block$min_n %||% 100L)
  min_items <- as.integer(block$min_items_per_construct %||% 2L)
  min_constructs <- as.integer(block$min_constructs %||% 2L)
  w <- character()
  cons <- block$constructs
  paths <- block$paths
  if (is.null(cons) || length(cons) < 1L) {
    return(list(
      type = "pls_sem",
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list("PLS-SEM skipped: không có constructs."),
      gates = list()
    ))
  }
  n <- nrow(df)
  if (n < min_n) {
    w <- c(w, sprintf("n=%d < min_n=%d (gate PLS).", n, min_n))
  }
  ind_all <- character()
  for (co in cons) {
    inds <- unlist(co$indicators)
    mode <- co$mode %||% "reflective"
    nm <- co$name %||% "unnamed"
    if (!identical(mode, "reflective")) {
      w <- c(w, sprintf("Construct '%s': chỉ hỗ trợ mode=reflective trong Phase 5.", nm))
      next
    }
    ind_all <- c(ind_all, inds)
    if (length(inds) < min_items) {
      w <- c(w, sprintf("Construct '%s': %d chỉ số < min_items_per_construct=%d.", nm, length(inds), min_items))
    }
  }
  if (length(cons) < min_constructs) {
    w <- c(w, sprintf("Số construct=%d < min_constructs=%d.", length(cons), min_constructs))
  }
  miss <- setdiff(unique(ind_all), names(df))
  if (length(miss) > 0) {
    w <- c(w, paste("Thiếu cột:", paste(miss, collapse = ", ")))
  }
  if (is.null(paths) || length(paths) < 1L) {
    w <- c(w, "Không có structural paths — bỏ qua ước lượng PLS.")
  }
  if (length(w) > 0) {
    return(list(
      type = "pls_sem",
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = as.list(w),
      gates = list(n = n, min_n = min_n, min_items_per_construct = min_items, min_constructs = min_constructs)
    ))
  }
  d <- df[, unique(ind_all), drop = FALSE]
  d[] <- lapply(d, function(x) if (is.numeric(x)) x else suppressWarnings(as.numeric(x)))
  cc <- stats::complete.cases(d)
  n2 <- sum(cc)
  if (n2 < min_n) {
    return(list(
      type = "pls_sem",
      ok = TRUE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(sprintf("Sau listwise trên chỉ số: n=%d < min_n=%d.", n2, min_n)),
      gates = list(n = n2, min_n = min_n)
    ))
  }
  d2 <- d[cc, , drop = FALSE]
  mm_parts <- list()
  for (co in cons) {
    inds <- unlist(co$indicators)
    nm <- co$name
    mm_parts[[length(mm_parts) + 1L]] <- seminr::reflective(nm, inds)
  }
  mm <- do.call(seminr::constructs, mm_parts)
  # seminr >= 2.4: paths(from=, to=); không dùng seminr::from()/to() (không export).
  pr <- lapply(paths, function(p) {
    seminr::paths(from = unlist(p$from), to = unlist(p$to))
  })
  sm <- do.call(seminr::relationships, pr)
  est <- tryCatch(
    seminr::estimate_pls(d2, mm, sm),
    error = function(e) list(error = conditionMessage(e))
  )
  if (!is.null(est$error)) {
    return(list(
      type = "pls_sem",
      ok = FALSE,
      ran = FALSE,
      skipped = TRUE,
      warnings = list(est$error),
      gates = list()
    ))
  }
  # summary() có thể lỗi khi path_coef có NaN (PLSc / mẫu nhỏ) — vẫn trả path_coef từ object.
  sm_wrap <- tryCatch(
    list(ok = TRUE, obj = suppressWarnings(summary(est))),
    error = function(e) list(ok = FALSE, err = conditionMessage(e))
  )
  pcoef <- NULL
  if (isTRUE(sm_wrap$ok)) {
    pcoef <- tryCatch(
      as.data.frame(sm_wrap$obj$paths),
      error = function(e) NULL
    )
  }
  if (is.null(pcoef)) {
    pcoef <- tryCatch(as.data.frame(est$path_coef), error = function(e) NULL)
  }
  if (is.null(pcoef)) {
    pcoef <- data.frame()
  }
  pls_warn <- character()
  if (!isTRUE(sm_wrap$ok)) {
    pls_warn <- c(
      pls_warn,
      paste0(
        "PLS đã ước lượng nhưng summary(seminr) lỗi (thường do NaN trong PLSc / cỡ mẫu nhỏ): ",
        sm_wrap$err
      )
    )
  }
  list(
    type = "pls_sem",
    ok = TRUE,
    ran = TRUE,
    skipped = FALSE,
    n = n2,
    path_coef = pcoef,
    warnings = as.list(pls_warn),
    gates = list(min_n = min_n, min_items_per_construct = min_items)
  )
}
