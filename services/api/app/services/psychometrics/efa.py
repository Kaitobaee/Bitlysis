"""Exploratory Factor Analysis (EFA) thuần numpy/scipy.

Tránh phụ thuộc `factor_analyzer` (0.5.1 hỏng với sklearn >=1.6) bằng cách:
- KMO & Bartlett tự cài đặt từ ma trận tương quan.
- Principal Axis Factoring (PAF) lặp trên reduced correlation matrix với khởi
  tạo communalities = SMC (squared multiple correlation).
- Xoay Varimax (Kaiser) bằng SVD compact (Harman/Kaiser).

Tham chiếu: Harman (1976) Modern Factor Analysis; Hair et al. (2014).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _coerce_numeric(df: pd.DataFrame, items: list[str]) -> pd.DataFrame:
    sub = df[items].copy()
    for c in sub.columns:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    return sub


def _smc(corr: np.ndarray) -> np.ndarray:
    """Squared Multiple Correlation = 1 - 1/diag(inv(R)); clip [0, 1]."""
    try:
        inv_r = np.linalg.pinv(corr)
        diag_inv = np.diag(inv_r)
        smc = 1.0 - 1.0 / np.where(diag_inv == 0, 1.0, diag_inv)
        return np.clip(smc, 0.0, 0.999)
    except np.linalg.LinAlgError:
        return np.full(corr.shape[0], 0.5)


def _kmo(corr: np.ndarray) -> tuple[float | None, np.ndarray]:
    try:
        inv_r = np.linalg.pinv(corr)
    except np.linalg.LinAlgError:
        return None, np.array([])
    k = corr.shape[0]
    # Partial correlation matrix Q.
    diag = np.diag(inv_r)
    if np.any(diag <= 0):
        return None, np.array([])
    d_sqrt = np.sqrt(diag)
    q = -inv_r / np.outer(d_sqrt, d_sqrt)
    np.fill_diagonal(q, 0.0)
    r_offdiag = corr.copy()
    np.fill_diagonal(r_offdiag, 0.0)
    sum_r2 = float(np.sum(r_offdiag**2))
    sum_q2 = float(np.sum(q**2))
    denom = sum_r2 + sum_q2
    total = sum_r2 / denom if denom > 0 else None

    per_item = np.full(k, np.nan)
    for j in range(k):
        r_col = r_offdiag[j, :]
        q_col = q[j, :]
        r2 = float(np.sum(r_col**2))
        q2 = float(np.sum(q_col**2))
        d = r2 + q2
        if d > 0:
            per_item[j] = r2 / d
    return float(total) if total is not None else None, per_item


def _bartlett(corr: np.ndarray, n: int) -> tuple[float | None, float | None, int]:
    """Bartlett's test of sphericity (Wilks LRT)."""
    k = corr.shape[0]
    df = k * (k - 1) // 2
    sign, logdet = np.linalg.slogdet(corr)
    if sign <= 0 or not np.isfinite(logdet):
        return None, None, df
    chi2 = -(n - 1 - (2 * k + 5) / 6.0) * float(logdet)
    if chi2 < 0 or df <= 0:
        return float(chi2), None, df
    from scipy.stats import chi2 as chi2_dist
    p = float(1.0 - chi2_dist.cdf(chi2, df))
    return float(chi2), p, df


def _paf(corr: np.ndarray, n_factors: int, *, max_iter: int = 100, tol: float = 1e-5) -> np.ndarray:
    """Principal Axis Factoring: trả loadings p×k chưa rotate."""
    h2 = _smc(corr).astype(float)
    R = corr.copy()
    for _ in range(max_iter):
        np.fill_diagonal(R, h2)
        eigvals, eigvecs = np.linalg.eigh(R)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]
        # Giữ k eigenvector lớn nhất; clip ev âm về 0 cho phép tính (Heywood case).
        ev_top = np.clip(eigvals[:n_factors], 0.0, None)
        loadings = eigvecs[:, :n_factors] * np.sqrt(ev_top)
        new_h2 = np.sum(loadings**2, axis=1)
        new_h2 = np.clip(new_h2, 0.0, 1.0)
        if np.max(np.abs(new_h2 - h2)) < tol:
            h2 = new_h2
            break
        h2 = new_h2
    return loadings


def _varimax(loadings: np.ndarray, *, max_iter: int = 100, tol: float = 1e-8) -> np.ndarray:
    """Varimax rotation (Kaiser) — compact SVD form."""
    p, k = loadings.shape
    if k < 2:
        return loadings.copy()
    R = np.eye(k)
    d_old = 0.0
    L = loadings.copy()
    for _ in range(max_iter):
        Lambda = L @ R
        u, s, vh = np.linalg.svd(
            L.T
            @ (Lambda**3 - (1.0 / p) * Lambda @ np.diag(np.sum(Lambda**2, axis=0))),
            full_matrices=False,
        )
        R = u @ vh
        d = float(np.sum(s))
        if d_old != 0 and abs(d - d_old) / max(d_old, 1e-12) < tol:
            break
        d_old = d
    return L @ R


def run_efa(df: pd.DataFrame, block: dict[str, Any]) -> dict[str, Any]:
    variables = list(block.get("variables") or [])
    k = int(block.get("n_factors") or 2)
    min_vars = int(block.get("min_variables") or 3)
    min_n = int(block.get("min_n") or 10)
    rotation = str(block.get("rotation") or "varimax").lower()

    if len(variables) < min_vars:
        return {
            "type": "efa",
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": [
                f"EFA skipped: {len(variables)} biến < min_variables={min_vars}",
            ],
            "gates": {"n_vars": len(variables), "min_variables": min_vars},
        }
    missing = [c for c in variables if c not in df.columns]
    if missing:
        return {
            "type": "efa",
            "ok": False,
            "ran": False,
            "skipped": True,
            "warnings": [f"Thiếu cột: {', '.join(missing)}"],
            "gates": {},
        }
    sub = _coerce_numeric(df, variables).dropna(how="any")
    n_ok = int(len(sub))
    if n_ok < min_n:
        return {
            "type": "efa",
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": [f"EFA skipped: n={n_ok} < min_n={min_n}"],
            "gates": {"n": n_ok, "min_n": min_n},
        }

    arr = sub.to_numpy(dtype=float)
    variances = np.var(arr, axis=0, ddof=1)
    zero_cols = [variables[i] for i, v in enumerate(variances) if not np.isfinite(v) or v <= 0]
    if zero_cols:
        return {
            "type": "efa",
            "ok": False,
            "ran": False,
            "skipped": True,
            "warnings": [f"Cột phương sai = 0: {', '.join(zero_cols)}"],
            "gates": {"n": n_ok},
        }
    if k >= arr.shape[1]:
        return {
            "type": "efa",
            "ok": False,
            "ran": False,
            "skipped": True,
            "warnings": [f"n_factors={k} ≥ số biến {arr.shape[1]}; chọn k nhỏ hơn."],
            "gates": {},
        }

    corr = np.corrcoef(arr, rowvar=False)
    eigvals_full = sorted(
        [float(v) for v in np.linalg.eigvalsh(corr).tolist()],
        reverse=True,
    )

    kmo_total, kmo_each = _kmo(corr)
    chi2_b, p_b, df_b = _bartlett(corr, n_ok)

    try:
        loadings_unrot = _paf(corr, n_factors=k)
    except np.linalg.LinAlgError as exc:
        return {
            "type": "efa",
            "ok": False,
            "ran": False,
            "skipped": True,
            "warnings": [f"PAF eigendecomp lỗi: {exc}"],
            "gates": {},
        }

    if rotation == "varimax":
        loadings = _varimax(loadings_unrot)
        rot_label = "varimax"
    else:
        loadings = loadings_unrot
        rot_label = "none"

    communalities = np.sum(loadings**2, axis=1)
    ssl = np.sum(loadings**2, axis=0)
    total_var = float(arr.shape[1])
    var_prop = ssl / total_var if total_var > 0 else np.zeros_like(ssl)
    cum_prop = np.cumsum(var_prop)

    loading_rows: list[dict[str, Any]] = []
    for i, name in enumerate(variables):
        row: dict[str, Any] = {"item": str(name)}
        for j in range(k):
            row[f"F{j + 1}"] = float(loadings[i, j])
        loading_rows.append(row)

    return {
        "type": "efa",
        "ok": True,
        "ran": True,
        "skipped": False,
        "n": n_ok,
        "n_factors": k,
        "rotation": rot_label,
        "method": "paf",
        "loadings": loading_rows,
        "communalities": [
            {"item": str(v), "communality": float(c)}
            for v, c in zip(variables, communalities, strict=True)
        ],
        "variance_proportion": [float(v) for v in var_prop.tolist()],
        "cumulative_variance": [float(v) for v in cum_prop.tolist()],
        "ssl_loadings": [float(v) for v in ssl.tolist()],
        "eigenvalues": eigvals_full,
        "scree_plot": [
            {"factor_index": i + 1, "eigenvalue": v}
            for i, v in enumerate(eigvals_full)
        ],
        "factor_correlation_matrix": [],
        "kmo_bartlett": {
            "kmo_total": kmo_total,
            "kmo_per_item": [
                {
                    "item": str(v),
                    "kmo": (
                        float(kmo_each[i])
                        if kmo_each.size and np.isfinite(kmo_each[i])
                        else None
                    ),
                }
                for i, v in enumerate(variables)
            ],
            "bartlett_chi_square": chi2_b,
            "bartlett_p_value": p_b,
            "bartlett_df": df_b,
        },
        "warnings": [],
        "gates": {"min_variables": min_vars, "min_n": min_n},
    }
