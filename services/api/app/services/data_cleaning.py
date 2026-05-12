"""Bước làm sạch dữ liệu có log, chạy giữa profiling và analyze.

Trả về `(df_clean, cleaning_log, cleaning_summary)`:
- `df_clean`: DataFrame sau khi chuẩn hoá dtype, xử lý missing/outlier theo
  chính sách cấu hình.
- `cleaning_log`: list các action có structured detail (để hiển thị UI minh bạch).
- `cleaning_summary`: dict cho manifest/JSON (counts trước/sau, policy đã áp dụng).

Không impute im lặng: mọi thay đổi đều ghi vào log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

MissingPolicy = Literal["report_only", "drop_row", "drop_column", "impute_median", "impute_mean"]
OutlierPolicy = Literal["report_only", "winsorize", "remove"]


@dataclass
class CleaningOptions:
    missing_policy: MissingPolicy = "report_only"
    missing_drop_column_threshold: float = 0.5
    """Drop column nếu missing_pct vượt ngưỡng (0..1)."""
    outlier_policy: OutlierPolicy = "report_only"
    outlier_iqr_multiplier: float = 1.5
    numeric_coercion_threshold: float = 0.8
    """Nếu ≥ ngưỡng tỷ lệ giá trị object ép numeric được, đổi dtype thành float."""
    datetime_coercion_threshold: float = 0.9
    """Tỷ lệ giá trị ép datetime được thì coi như cột thời gian."""
    enabled: bool = True


@dataclass
class CleaningLogEntry:
    action: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _coerce_dtypes(
    df: pd.DataFrame,
    opts: CleaningOptions,
    log: list[CleaningLogEntry],
) -> pd.DataFrame:
    out = df.copy()
    changed_numeric: list[str] = []
    changed_datetime: list[str] = []
    for col in out.columns:
        series = out[col]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue
        if pd.api.types.is_bool_dtype(series):
            continue
        # Try numeric coercion.
        coerced_num = pd.to_numeric(series, errors="coerce")
        valid_num = float(coerced_num.notna().mean()) if len(series) else 0.0
        # Try datetime coercion.
        try:
            coerced_dt = pd.to_datetime(series, errors="coerce", utc=False, format="mixed")
        except (ValueError, TypeError):
            coerced_dt = pd.Series([pd.NaT] * len(series), index=series.index)
        valid_dt = float(coerced_dt.notna().mean()) if len(series) else 0.0
        if valid_dt >= opts.datetime_coercion_threshold and valid_dt >= valid_num:
            out[col] = coerced_dt
            changed_datetime.append(str(col))
        elif valid_num >= opts.numeric_coercion_threshold and coerced_num.notna().sum() >= 5:
            out[col] = coerced_num
            changed_numeric.append(str(col))
    if changed_numeric:
        log.append(
            CleaningLogEntry(
                action="coerce_dtype_numeric",
                detail=f"Ép {len(changed_numeric)} cột object → numeric",
                evidence={
                    "columns": changed_numeric,
                    "threshold": opts.numeric_coercion_threshold,
                },
            )
        )
    if changed_datetime:
        log.append(
            CleaningLogEntry(
                action="coerce_dtype_datetime",
                detail=f"Ép {len(changed_datetime)} cột object → datetime",
                evidence={
                    "columns": changed_datetime,
                    "threshold": opts.datetime_coercion_threshold,
                },
            )
        )
    return out


def _apply_missing_policy(
    df: pd.DataFrame,
    opts: CleaningOptions,
    log: list[CleaningLogEntry],
) -> pd.DataFrame:
    out = df
    n_rows = len(out)
    miss_report = {
        str(c): {
            "missing_count": int(out[c].isna().sum()),
            "missing_pct": float(out[c].isna().mean()) if n_rows else 0.0,
        }
        for c in out.columns
    }
    log.append(
        CleaningLogEntry(
            action="missing_value_report",
            detail="Bảng tỷ lệ missing trước khi áp dụng chính sách.",
            evidence={"per_column": miss_report, "rows": n_rows},
        )
    )

    policy = opts.missing_policy
    if policy == "report_only" or n_rows == 0:
        return out

    cols_to_drop = [
        c
        for c, info in miss_report.items()
        if info["missing_pct"] >= opts.missing_drop_column_threshold
    ]
    if cols_to_drop:
        out = out.drop(columns=cols_to_drop)
        pct = opts.missing_drop_column_threshold
        log.append(
            CleaningLogEntry(
                action="drop_columns_high_missing",
                detail=f"Bỏ {len(cols_to_drop)} cột missing ≥ {pct:.0%}",
                evidence={"columns": cols_to_drop},
            )
        )

    if policy == "drop_row":
        before = len(out)
        out = out.dropna(how="any")
        log.append(
            CleaningLogEntry(
                action="drop_rows_any_na",
                detail=f"Bỏ {before - len(out)} dòng còn missing.",
                evidence={"rows_before": before, "rows_after": len(out)},
            )
        )
    elif policy == "drop_column":
        # Đã drop ở trên; không làm gì thêm.
        return out
    elif policy in {"impute_median", "impute_mean"}:
        imputed: dict[str, dict[str, Any]] = {}
        for col in out.columns:
            series = out[col]
            n_missing = int(series.isna().sum())
            if n_missing == 0:
                continue
            if pd.api.types.is_numeric_dtype(series):
                value = (
                    float(series.median())
                    if policy == "impute_median"
                    else float(series.mean())
                )
                out[col] = series.fillna(value)
                imputed[str(col)] = {
                    "n_imputed": n_missing,
                    "policy": policy,
                    "value": value,
                }
            else:
                mode = series.mode(dropna=True)
                if not mode.empty:
                    fill = mode.iloc[0]
                    out[col] = series.fillna(fill)
                    imputed[str(col)] = {
                        "n_imputed": n_missing,
                        "policy": "impute_mode",
                        "value": str(fill),
                    }
        if imputed:
            log.append(
                CleaningLogEntry(
                    action="impute_missing",
                    detail=f"Impute {len(imputed)} cột (numeric={policy}, categorical=mode).",
                    evidence={"per_column": imputed},
                )
            )
    return out


def _apply_outlier_policy(
    df: pd.DataFrame,
    opts: CleaningOptions,
    log: list[CleaningLogEntry],
) -> pd.DataFrame:
    out = df
    multiplier = float(opts.outlier_iqr_multiplier)
    bounds: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for col in out.select_dtypes(include=[np.number]).columns:
        series = out[col].dropna()
        if len(series) < 4:
            continue
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo = q1 - multiplier * iqr
        hi = q3 + multiplier * iqr
        mask = (out[col] < lo) | (out[col] > hi)
        n = int(mask.sum())
        bounds[str(col)] = {"low": lo, "high": hi, "iqr": iqr}
        counts[str(col)] = n
    log.append(
        CleaningLogEntry(
            action="outlier_report",
            detail=f"IQR {multiplier}× — báo cáo {sum(counts.values())} điểm vượt biên.",
            evidence={"per_column_counts": counts, "bounds": bounds},
        )
    )
    if opts.outlier_policy == "report_only" or not bounds:
        return out
    if opts.outlier_policy == "winsorize":
        for col, bd in bounds.items():
            out[col] = out[col].clip(lower=bd["low"], upper=bd["high"])
        log.append(
            CleaningLogEntry(
                action="winsorize_outliers",
                detail=f"Winsorize {len(bounds)} cột về biên IQR.",
                evidence={"per_column_bounds": bounds},
            )
        )
    elif opts.outlier_policy == "remove":
        before = len(out)
        mask_all = pd.Series(False, index=out.index)
        for col, bd in bounds.items():
            mask_all |= (out[col] < bd["low"]) | (out[col] > bd["high"])
        out = out[~mask_all]
        log.append(
            CleaningLogEntry(
                action="remove_outlier_rows",
                detail=f"Bỏ {before - len(out)} dòng chứa outlier (IQR {multiplier}×).",
                evidence={"rows_before": before, "rows_after": len(out)},
            )
        )
    return out


def clean_dataframe(
    df: pd.DataFrame,
    opts: CleaningOptions | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    options = opts or CleaningOptions()
    log: list[CleaningLogEntry] = []
    if not options.enabled:
        return df.copy(), [], {"enabled": False}

    rows_before = int(len(df))
    cols_before = list(map(str, df.columns))

    work = _coerce_dtypes(df, options, log)
    work = _apply_missing_policy(work, options, log)
    work = _apply_outlier_policy(work, options, log)

    summary = {
        "enabled": True,
        "rows_before": rows_before,
        "rows_after": int(len(work)),
        "columns_before": cols_before,
        "columns_after": list(map(str, work.columns)),
        "missing_policy": options.missing_policy,
        "missing_drop_column_threshold": options.missing_drop_column_threshold,
        "outlier_policy": options.outlier_policy,
        "outlier_iqr_multiplier": options.outlier_iqr_multiplier,
        "numeric_coercion_threshold": options.numeric_coercion_threshold,
        "datetime_coercion_threshold": options.datetime_coercion_threshold,
    }
    log_serializable = [
        {"action": e.action, "detail": e.detail, "evidence": e.evidence}
        for e in log
    ]
    return work, log_serializable, summary
