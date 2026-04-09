from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd

from app.config import Settings
from app.schemas.stats import (
    CategoricalAssociationSpec,
    CompareGroupsNumericSpec,
    FullAutoAnalysisSpec,
)
from app.services.r_pipeline import run_r_pipeline_json
from app.services.stats_engine import (
    analyze_categorical_association,
    analyze_compare_groups_numeric,
)


def _is_numeric_like(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series):
        return True
    if pd.api.types.is_bool_dtype(series):
        return False
    coerced = pd.to_numeric(series, errors="coerce")
    valid_ratio = float(coerced.notna().mean()) if len(series) else 0.0
    return valid_ratio >= 0.8 and coerced.notna().sum() >= 5


def _collect_roles(df: pd.DataFrame) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    column_details: list[dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        missing_count = int(series.isna().sum())
        nunique = int(series.nunique(dropna=True))
        if series.nunique(dropna=True) <= 1:
            role = "constant"
        elif _is_numeric_like(series):
            role = "numeric"
            numeric_cols.append(str(col))
        else:
            role = "categorical"
            categorical_cols.append(str(col))
        column_details.append(
            {
                "name": str(col),
                "dtype": str(series.dtype),
                "missing_count": missing_count,
                "nunique": nunique,
                "role": role,
            }
        )

    return numeric_cols, categorical_cols, column_details


def _build_r_analyses(numeric_cols: list[str]) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []
    if len(numeric_cols) >= 2:
        analyses.append(
            {
                "type": "cronbach_alpha",
                "scale_id": "all_numeric_block",
                "items": numeric_cols,
            }
        )
    if len(numeric_cols) >= 3:
        analyses.append(
            {
                "type": "efa",
                "variables": numeric_cols,
                "n_factors": min(3, max(2, len(numeric_cols) - 1)),
                "min_variables": 3,
                "min_n": 10,
            }
        )
    return analyses


def _run_r_block(
    settings: Settings,
    df: pd.DataFrame,
    numeric_cols: list[str],
    prefer_r: bool,
) -> dict[str, Any]:
    if not prefer_r:
        return {
            "available": False,
            "preferred": False,
            "reason": "R bị tắt bởi cấu hình full_auto_analysis",
            "results": [],
        }
    if len(numeric_cols) < 2:
        return {
            "available": False,
            "preferred": True,
            "reason": "Không đủ cột numeric để chạy R",
            "results": [],
        }

    analyses = _build_r_analyses(numeric_cols)
    if not analyses:
        return {
            "available": False,
            "preferred": prefer_r,
            "reason": "Không có phân tích R phù hợp cho dữ liệu hiện tại",
            "results": [],
        }

    try:
        parsed, stderr, rc = run_r_pipeline_json(settings, df[numeric_cols].copy(), analyses)
    except FileNotFoundError as e:
        return {
            "available": False,
            "preferred": prefer_r,
            "reason": str(e),
            "results": [],
        }

    return {
        "available": bool(parsed.get("ok")) and rc == 0,
        "preferred": prefer_r,
        "returncode": rc,
        "stderr": (stderr or "")[:8000],
        "results": parsed.get("results", []),
        "error": None if parsed.get("ok") and rc == 0 else parsed.get("error"),
    }


def _build_pairwise_categorical(
    df: pd.DataFrame,
    categorical_cols: list[str],
    max_pairs: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pairs = list(combinations(categorical_cols, 2))
    for a, b in pairs[:max_pairs]:
        try:
            results.append(
                {
                    "kind": "categorical_association",
                    "variable_a": a,
                    "variable_b": b,
                    "analysis": analyze_categorical_association(
                        df,
                        CategoricalAssociationSpec(
                            kind="categorical_association",
                            variable_a=a,
                            variable_b=b,
                        ),
                    ),
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "kind": "categorical_association",
                    "variable_a": a,
                    "variable_b": b,
                    "error": str(e),
                }
            )
    return results


def _build_mixed_comparisons(
    df: pd.DataFrame,
    numeric_cols: list[str],
    categorical_cols: list[str],
    max_items: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    candidates: list[tuple[str, str]] = []
    for outcome in numeric_cols:
        for group in categorical_cols:
            grp_nunique = int(df[group].nunique(dropna=True))
            if 2 <= grp_nunique <= 5:
                candidates.append((outcome, group))
    for outcome, group in candidates[:max_items]:
        try:
            results.append(
                {
                    "kind": "compare_groups_numeric",
                    "outcome": outcome,
                    "group": group,
                    "analysis": analyze_compare_groups_numeric(
                        df,
                        CompareGroupsNumericSpec(
                            kind="compare_groups_numeric",
                            outcome=outcome,
                            group=group,
                        ),
                    ),
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "kind": "compare_groups_numeric",
                    "outcome": outcome,
                    "group": group,
                    "error": str(e),
                }
            )
    return results


def run_full_auto_analysis(
    settings: Settings,
    df: pd.DataFrame,
    spec: FullAutoAnalysisSpec,
) -> dict[str, Any]:
    numeric_cols, categorical_cols, column_details = _collect_roles(df)
    overview = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "constant_columns": [c["name"] for c in column_details if c["role"] == "constant"],
        "column_details": column_details,
    }

    warnings: list[str] = []
    r_block = _run_r_block(settings, df, numeric_cols, spec.prefer_r)
    if not r_block.get("available") and r_block.get("reason"):
        # Chỉ đẩy lỗi thực sự ra warnings; trường hợp thiếu numeric là trạng thái dữ liệu.
        if len(numeric_cols) >= 2:
            warnings.append(f"R không chạy cho khối numeric: {r_block['reason']}")

    cat_results = _build_pairwise_categorical(
        df,
        categorical_cols,
        spec.max_categorical_pairs,
    )
    mix_results = _build_mixed_comparisons(
        df,
        numeric_cols,
        categorical_cols,
        spec.max_group_comparisons,
    )

    sections: dict[str, Any] = {
        "overview": overview,
        "r_block": r_block,
        "categorical_associations": cat_results,
        "mixed_group_comparisons": mix_results,
    }

    highlights: list[str] = []
    if r_block.get("available"):
        highlights.append("Khối numeric đã được xử lý bằng R.")
    elif numeric_cols:
        highlights.append("Khối numeric được chuyển sang chế độ dự phòng.")
    if categorical_cols:
        highlights.append(f"Có {len(categorical_cols)} cột categorical được kiểm tra.")
    total_cat_pairs = len(list(combinations(categorical_cols, 2)))
    if total_cat_pairs > spec.max_categorical_pairs:
        highlights.append(f"Chỉ hiển thị {spec.max_categorical_pairs} cặp categorical tiêu biểu.")
    if mix_results:
        highlights.append(f"Có {len(mix_results)} so sánh numeric vs categorical.")

    engine_name = "auto_full_analysis_r" if r_block.get("available") else "auto_full_analysis"

    return {
        "engine": engine_name,
        "version": 7,
        "spec": spec.model_dump(mode="json"),
        "highlights": highlights,
        "warnings": warnings,
        "analysis_sections": sections,
    }
