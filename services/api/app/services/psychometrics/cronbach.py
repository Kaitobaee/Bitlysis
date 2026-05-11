"""Cronbach's alpha (raw + standardized) thuần Python.

Gate khớp với `bitlysis_run_cronbach` trong package R cũ:
- < 2 item: skipped.
- Thiếu cột: ok=False, skipped.
- Sau ép numeric + listwise complete cases < 2: skipped.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _coerce_numeric(df: pd.DataFrame, items: list[str]) -> pd.DataFrame:
    sub = df[items].copy()
    for c in sub.columns:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    return sub


def _alpha_from_matrix(arr: np.ndarray) -> tuple[float, float]:
    """Trả (raw_alpha, std_alpha). Yêu cầu arr không có NaN."""
    k = arr.shape[1]
    if k < 2:
        return float("nan"), float("nan")
    item_var = np.var(arr, axis=0, ddof=1)
    total = arr.sum(axis=1)
    total_var = float(np.var(total, ddof=1))
    if total_var <= 0:
        raw_alpha = float("nan")
    else:
        raw_alpha = float((k / (k - 1.0)) * (1.0 - float(item_var.sum()) / total_var))

    # Standardized alpha: dựa trên correlation matrix.
    corr = np.corrcoef(arr, rowvar=False)
    if not np.all(np.isfinite(corr)):
        return raw_alpha, float("nan")
    # Trung bình các tương quan off-diagonal.
    iu = np.triu_indices(k, k=1)
    r_bar = float(np.mean(corr[iu])) if iu[0].size else float("nan")
    if not np.isfinite(r_bar):
        return raw_alpha, float("nan")
    denom = 1.0 + (k - 1.0) * r_bar
    if denom == 0:
        return raw_alpha, float("nan")
    std_alpha = float((k * r_bar) / denom)
    return raw_alpha, std_alpha


def _item_total_stats(arr: np.ndarray, raw_alpha: float) -> list[dict[str, Any]]:
    k = arr.shape[1]
    rows: list[dict[str, Any]] = []
    total = arr.sum(axis=1)
    for j in range(k):
        rest = total - arr[:, j]
        std_j = float(np.std(arr[:, j], ddof=1))
        std_rest = float(np.std(rest, ddof=1))
        if std_j == 0 or std_rest == 0:
            r_it = float("nan")
        else:
            r_it = float(np.corrcoef(arr[:, j], rest)[0, 1])
        # alpha nếu drop item j
        if k - 1 >= 2:
            other = np.delete(arr, j, axis=1)
            a_drop, _ = _alpha_from_matrix(other)
        else:
            a_drop = float("nan")
        rows.append({
            "item_index": j,
            "item_total_corr": None if not np.isfinite(r_it) else r_it,
            "alpha_if_dropped": None if not np.isfinite(a_drop) else a_drop,
        })
    return rows


def run_cronbach(df: pd.DataFrame, block: dict[str, Any]) -> dict[str, Any]:
    items = list(block.get("items") or [])
    scale_id = str(block.get("scale_id") or "scale")

    if len(items) < 2:
        return {
            "type": "cronbach_alpha",
            "scale_id": scale_id,
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": ["Cần ít nhất 2 biến cho Cronbach alpha."],
            "gates": {"min_items": 2, "n_items": len(items)},
        }

    missing = [c for c in items if c not in df.columns]
    if missing:
        return {
            "type": "cronbach_alpha",
            "scale_id": scale_id,
            "ok": False,
            "ran": False,
            "skipped": True,
            "warnings": [f"Thiếu cột: {', '.join(missing)}"],
            "gates": {},
        }

    sub = _coerce_numeric(df, items).dropna(how="any")
    n_ok = int(len(sub))
    if n_ok < 2:
        return {
            "type": "cronbach_alpha",
            "scale_id": scale_id,
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": ["Không đủ quan sát hoàn chỉnh sau khi ép numeric."],
            "gates": {"n_complete": n_ok},
        }

    arr = sub.to_numpy(dtype=float)
    raw_alpha, std_alpha = _alpha_from_matrix(arr)
    item_stats = _item_total_stats(arr, raw_alpha)
    for row, name in zip(item_stats, items, strict=True):
        row["item"] = str(name)

    return {
        "type": "cronbach_alpha",
        "scale_id": scale_id,
        "ok": True,
        "ran": True,
        "skipped": False,
        "raw_alpha": None if not np.isfinite(raw_alpha) else float(raw_alpha),
        "std_alpha": None if not np.isfinite(std_alpha) else float(std_alpha),
        "n": n_ok,
        "items": [str(c) for c in items],
        "item_total_statistics": item_stats,
        "warnings": [],
        "gates": {"min_items": 2},
    }
