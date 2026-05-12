"""Comprehensive analysis orchestrator (Phase 3).

Pipeline cố định:
1. Profiling đã có sẵn từ upload (`raw["profiling"]`, `raw["profiling_detail"]`).
2. `data_cleaning.clean_dataframe`.
3. Phân loại role cột (numeric / categorical / datetime / likert).
4. Sinh giả thuyết: rule-based + LLM optional (chỉ paraphrase, không thay engine).
5. Dispatcher chạy stats_engine / psychometrics / timeseries theo loại biến.
6. Gom thành schema thống nhất (`academic_summary`, `hypothesis_table`,
   `decision_trace`, `diagnostics`, `evidence`, `charts`, `results`,
   `provenance_ref`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from app.config import Settings
from app.schemas.stats import (
    CategoricalAssociationSpec,
    CompareGroupsNumericSpec,
    ComprehensiveAnalysisSpec,
    RegressionOLSSpec,
    TimeSeriesSpec,
)
from app.services.data_cleaning import CleaningOptions, clean_dataframe
from app.services.provenance import engine_versions, infer_repo_root, pip_lock_sha256
from app.services.psychometrics import ENGINE_ID as PSYCHO_ENGINE_ID
from app.services.psychometrics import run_psychometrics
from app.services.stats_engine import (
    analyze_categorical_association,
    analyze_compare_groups_numeric,
    analyze_regression_ols,
    build_basic_analysis,
)
from app.services.timeseries_engine import run_timeseries_analysis

logger = logging.getLogger(__name__)

ENGINE_ID = "bitlysis_comprehensive_analysis"
ENGINE_VERSION = 1


# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------

def _detect_roles(df: pd.DataFrame) -> dict[str, Any]:
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    datetime_cols: list[str] = []
    likert_cols: list[str] = []
    constant_cols: list[str] = []
    details: list[dict[str, Any]] = []
    for col in df.columns:
        series = df[col]
        nunique = int(series.nunique(dropna=True))
        missing = int(series.isna().sum())
        if pd.api.types.is_datetime64_any_dtype(series):
            role = "datetime"
            datetime_cols.append(str(col))
        elif nunique <= 1:
            role = "constant"
            constant_cols.append(str(col))
        elif pd.api.types.is_numeric_dtype(series):
            # Likert: integers in 1..7 or 1..10, between 3 và 10 mức duy nhất.
            values = series.dropna()
            uniques = sorted(values.unique().tolist())
            is_intish = all(float(v).is_integer() for v in uniques if np.isfinite(v))
            in_likert_range = (
                is_intish
                and len(uniques) >= 3
                and len(uniques) <= 10
                and min(uniques) >= 1
                and max(uniques) <= 10
            )
            if in_likert_range:
                likert_cols.append(str(col))
                role = "likert"
            else:
                role = "numeric"
                numeric_cols.append(str(col))
        else:
            # Treat low-cardinality string as categorical; high-cardinality as
            # generic categorical (unsuitable for analysis without grouping).
            role = "categorical"
            categorical_cols.append(str(col))
        details.append(
            {
                "name": str(col),
                "dtype": str(series.dtype),
                "nunique": nunique,
                "missing_count": missing,
                "role": role,
            }
        )
    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "datetime": datetime_cols,
        "likert": likert_cols,
        "constant": constant_cols,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Auto-build analysis batches
# ---------------------------------------------------------------------------

def _build_psychometrics_batch(roles: dict[str, Any]) -> list[dict[str, Any]]:
    """Cronbach + EFA trên toàn bộ cột Likert (gộp 1 scale)."""
    likert = list(roles.get("likert") or [])
    out: list[dict[str, Any]] = []
    if len(likert) >= 2:
        out.append({
            "type": "cronbach_alpha",
            "scale_id": "all_likert",
            "items": likert,
        })
    if len(likert) >= 3:
        out.append({
            "type": "efa",
            "variables": likert,
            "n_factors": min(3, max(2, len(likert) - 1)),
            "min_variables": 3,
            "min_n": 10,
        })
    return out


def _build_auto_pls_batch(roles: dict[str, Any]) -> dict[str, Any] | None:
    """Khi đủ ≥6 cột Likert, đề xuất 1 mô hình PLS 2-construct heuristic.

    Chia đôi danh sách Likert thành KSI (predictor) → ETA (outcome). Đây là baseline
    minh hoạ; user nên gửi spec chi tiết qua `kind: "psychometrics"` để có cấu trúc
    construct/path thật.
    """
    likert = list(roles.get("likert") or [])
    if len(likert) < 6:
        return None
    half = len(likert) // 2
    ksi_items = likert[:half]
    eta_items = likert[half:]
    return {
        "type": "pls_sem",
        "min_n": 30,
        "min_items_per_construct": 2,
        "min_constructs": 2,
        "bootstrap_samples": 100,
        "constructs": [
            {"name": "KSI", "mode": "reflective", "indicators": ksi_items},
            {"name": "ETA", "mode": "reflective", "indicators": eta_items},
        ],
        "paths": [{"from": "KSI", "to": "ETA"}],
    }


# ---------------------------------------------------------------------------
# Engine runners (wrap stats_engine for unified shape)
# ---------------------------------------------------------------------------

def _run_categorical_pairs(
    df: pd.DataFrame,
    cat_cols: list[str],
    max_pairs: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for a, b in list(combinations(cat_cols, 2))[:max_pairs]:
        try:
            res = analyze_categorical_association(
                df, CategoricalAssociationSpec(variable_a=a, variable_b=b)
            )
            results.append({"variable_a": a, "variable_b": b, "analysis": res})
        except Exception as exc:  # noqa: BLE001
            results.append({"variable_a": a, "variable_b": b, "error": str(exc)})
    return results


def _run_group_comparisons(
    df: pd.DataFrame,
    numeric_cols: list[str],
    cat_cols: list[str],
    max_items: int,
) -> list[dict[str, Any]]:
    candidates: list[tuple[str, str]] = []
    for outcome in numeric_cols:
        for group in cat_cols:
            try:
                nunique = int(df[group].nunique(dropna=True))
            except Exception:  # noqa: BLE001
                continue
            if 2 <= nunique <= 5:
                candidates.append((outcome, group))
    results: list[dict[str, Any]] = []
    for outcome, group in candidates[:max_items]:
        try:
            res = analyze_compare_groups_numeric(
                df, CompareGroupsNumericSpec(outcome=outcome, group=group)
            )
            results.append({"outcome": outcome, "group": group, "analysis": res})
        except Exception as exc:  # noqa: BLE001
            results.append({"outcome": outcome, "group": group, "error": str(exc)})
    return results


def _run_auto_regression(
    df: pd.DataFrame,
    numeric_cols: list[str],
) -> dict[str, Any] | None:
    """Một OLS heuristic: lấy 1 outcome + ≤3 predictor đầu tiên."""
    if len(numeric_cols) < 2:
        return None
    outcome = numeric_cols[0]
    preds = numeric_cols[1:4]
    if not preds:
        return None
    try:
        return {
            "outcome": outcome,
            "predictors": preds,
            "analysis": analyze_regression_ols(
                df, RegressionOLSSpec(outcome=outcome, predictors=preds)
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"outcome": outcome, "predictors": preds, "error": str(exc)}


def _run_auto_timeseries(
    df: pd.DataFrame,
    datetime_cols: list[str],
    numeric_cols: list[str],
) -> dict[str, Any] | None:
    if not datetime_cols or not numeric_cols:
        return None
    date_col = datetime_cols[0]
    value_col = numeric_cols[0]
    try:
        res = run_timeseries_analysis(
            df,
            TimeSeriesSpec(value_column=value_col, date_column=date_col),
        )
        return {"date_column": date_col, "value_column": value_col, "analysis": res}
    except Exception as exc:  # noqa: BLE001
        return {
            "date_column": date_col,
            "value_column": value_col,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Result mapping helpers
# ---------------------------------------------------------------------------

def _flatten_hypothesis_rows(*sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for src in sources:
        if not isinstance(src, list):
            continue
        for r in src:
            if isinstance(r, dict):
                rows.append(r)
    return rows


def _academic_summary(
    roles: dict[str, Any],
    methods_used: list[str],
    cleaning_summary: dict[str, Any],
    hypothesis_rows: list[dict[str, Any]],
    warnings_in: list[str],
) -> dict[str, Any]:
    n_numeric = len(roles["numeric"])
    n_cat = len(roles["categorical"])
    n_likert = len(roles["likert"])
    n_dt = len(roles["datetime"])
    pieces: list[str] = []
    if n_numeric:
        pieces.append(f"{n_numeric} biến định lượng")
    if n_cat:
        pieces.append(f"{n_cat} biến định tính")
    if n_likert:
        pieces.append(f"{n_likert} biến Likert")
    if n_dt:
        pieces.append(f"{n_dt} biến thời gian")
    data_type = ", ".join(pieces) if pieces else "Dữ liệu chưa phân loại được"

    rationale_parts: list[str] = []
    if n_likert >= 2 and "cronbach_alpha" in methods_used:
        rationale_parts.append("Likert đủ điều kiện → Cronbach α + EFA để đánh giá thang đo.")
    if n_likert >= 6 and "pls_sem" in methods_used:
        rationale_parts.append("Có ≥6 chỉ số Likert → đề xuất PLS-SEM heuristic 2 construct.")
    if n_numeric and n_cat and "compare_groups_numeric" in methods_used:
        rationale_parts.append("So sánh biến số theo nhóm khi có cột phân loại 2–5 cấp.")
    if n_cat >= 2 and "chi_square" in methods_used:
        rationale_parts.append("Hai cột phân loại → Chi-square / Cramér V.")
    if n_numeric >= 2 and "ols" in methods_used:
        rationale_parts.append("≥2 biến số → OLS heuristic xác định liên hệ tuyến tính.")
    if n_dt and n_numeric and "timeseries" in methods_used:
        rationale_parts.append("Có cột thời gian → forecasting ngắn hạn (ETS/ARIMA).")
    rationale = " ".join(rationale_parts) or "Chưa đủ dữ liệu để chọn phương pháp tự động."

    assumptions: list[str] = [
        "Quan sát độc lập (independent observations)",
        "Cleaning đã áp dụng theo policy: "
        + f"missing={cleaning_summary.get('missing_policy', 'report_only')}, "
        + f"outlier={cleaning_summary.get('outlier_policy', 'report_only')}",
    ]
    if "cronbach_alpha" in methods_used:
        assumptions.append("Thang đo đơn hướng cho Cronbach α (gộp item thực sự đo cùng concept).")
    if "ols" in methods_used:
        assumptions.append("OLS giả định tuyến tính + sai số đồng nhất; xem VIF/QQ.")

    reject = sum(1 for r in hypothesis_rows if r.get("decision") == "reject_h0")
    keep = sum(1 for r in hypothesis_rows if r.get("decision") == "fail_to_reject_h0")
    na = sum(1 for r in hypothesis_rows if r.get("decision") == "not_applicable")
    conclusion = (
        f"Đã chạy {len(hypothesis_rows)} kiểm định ({reject} bác bỏ H0, "
        f"{keep} không đủ bằng chứng bác bỏ, {na} không áp dụng được)."
    )

    return {
        "data_type": data_type,
        "methods": methods_used,
        "rationale": rationale,
        "assumptions": assumptions,
        "conclusion": conclusion,
        "warnings": warnings_in,
    }


def _map_psychometrics(parsed: dict[str, Any]) -> dict[str, Any]:
    """Local copy của mapper trong core/analysis.py (tránh circular import nặng)."""
    out: dict[str, Any] = {}
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        return out
    cronbach: list[dict[str, Any]] = []
    efa: list[dict[str, Any]] = []
    pls: list[dict[str, Any]] = []
    for block in results:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "cronbach_alpha":
            cronbach.append(block)
        elif t == "efa":
            efa.append(block)
        elif t == "pls_sem":
            pls.append(block)
    if cronbach:
        out["cronbach"] = cronbach
    if efa:
        out["efa"] = efa
        first = next((b for b in efa if b.get("ran")), efa[0])
        if first.get("loadings"):
            out["factor_loadings"] = first["loadings"]
        if first.get("kmo_bartlett"):
            out["kmo_bartlett"] = first["kmo_bartlett"]
        if first.get("scree_plot"):
            out["scree_plot"] = first["scree_plot"]
        if first.get("communalities"):
            out["communalities"] = first["communalities"]
        if first.get("variance_proportion"):
            out["variance_explained"] = first["variance_proportion"]
        if first.get("eigenvalues"):
            out["eigenvalues"] = first["eigenvalues"]
    if pls:
        out["pls_sem"] = pls
        first = next((b for b in pls if b.get("ran")), pls[0])
        if first.get("measurement_model"):
            out["measurement_model"] = first["measurement_model"]
        if first.get("structural_model"):
            out["structural_model"] = first["structural_model"]
            sm = first["structural_model"]
            if sm.get("path_coefficients"):
                out["path_coefficients"] = sm["path_coefficients"]
            if sm.get("r_squared"):
                out["r2"] = sm["r_squared"]
            if sm.get("q_squared"):
                out["q2"] = sm["q_squared"]
            if sm.get("f_squared"):
                out["f2"] = sm["f_squared"]
        if first.get("htmt"):
            out["htmt"] = first["htmt"]
        if first.get("fornell_larcker"):
            out["fornell_larcker"] = first["fornell_larcker"]
        if first.get("bootstrapping"):
            out["bootstrapping"] = first["bootstrapping"]
    return out


# ---------------------------------------------------------------------------
# Hypothesis suggestion helper
# ---------------------------------------------------------------------------

def _profiling_types_from_roles(roles: dict[str, Any]) -> dict[str, str]:
    profiling_types = {col: "numeric" for col in roles.get("numeric") or []}
    profiling_types.update({col: "categorical" for col in roles.get("categorical") or []})
    profiling_types.update({col: "likert" for col in roles.get("likert") or []})
    profiling_types.update({col: "datetime" for col in roles.get("datetime") or []})
    return profiling_types


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def run_comprehensive_analysis(
    settings: Settings,
    raw_job_meta: dict[str, Any],
    df: pd.DataFrame,
    spec: ComprehensiveAnalysisSpec,
) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    methods_used: list[str] = []

    # Phase 2 — cleaning
    cleaning_opts = CleaningOptions()  # mặc định report_only; không impute im lặng
    df_clean, cleaning_log, cleaning_summary = clean_dataframe(df, cleaning_opts)
    cleaned_at = datetime.now(UTC).isoformat()

    roles = _detect_roles(df_clean)
    overview = {
        "row_count": int(len(df_clean)),
        "column_count": int(len(df_clean.columns)),
        "numeric_columns": roles["numeric"],
        "categorical_columns": roles["categorical"],
        "likert_columns": roles["likert"],
        "datetime_columns": roles["datetime"],
        "constant_columns": roles["constant"],
        "column_details": roles["details"],
    }

    # Hypothesis suggestions (rule-based mặc định; LLM optional, chỉ paraphrase).
    column_names = [c for c in df_clean.columns.map(str).tolist()]
    from app.services.llm_hypotheses import suggest_hypotheses_from_profile

    try:
        suggestions, llm_meta = suggest_hypotheses_from_profile(
            settings,
            columns=column_names,
            profiling_types=_profiling_types_from_roles(roles),
            prefer_llm=bool(spec.enable_llm_hypotheses),
            httpx_client=None,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Hypothesis suggestion lỗi, dùng rule-based: {exc}")
        from app.services.llm_hypotheses import rule_based_hypotheses

        suggestions = [h.model_dump() for h in rule_based_hypotheses(column_names).hypotheses]
        llm_meta = {"source": "rule_based", "model": None, "warning": str(exc)}

    # Run engines
    sections: dict[str, Any] = {"overview": overview}

    # Psychometrics (Likert detection)
    psycho_parsed: dict[str, Any] = {}
    psycho_mapped: dict[str, Any] = {}
    if spec.enable_psychometrics and roles["likert"]:
        analyses = _build_psychometrics_batch(roles)
        if spec.enable_pls:
            pls_block = _build_auto_pls_batch(roles)
            if pls_block:
                analyses.append(pls_block)
        if analyses:
            psycho_parsed = run_psychometrics(df_clean, analyses, random_seed=spec.random_seed)
            psycho_mapped = _map_psychometrics(psycho_parsed)
            sections["psychometrics_block"] = {
                "available": True,
                "engine": psycho_parsed.get("engine"),
                "results": psycho_parsed.get("results", []),
            }
            if "cronbach_alpha" in {b.get("type") for b in analyses}:
                methods_used.append("cronbach_alpha")
            if "efa" in {b.get("type") for b in analyses}:
                methods_used.append("efa")
            if any(b.get("type") == "pls_sem" for b in analyses):
                methods_used.append("pls_sem")

    # Categorical pairs (chi-square)
    cat_pairs = _run_categorical_pairs(
        df_clean, roles["categorical"], spec.max_categorical_pairs
    )
    if cat_pairs:
        sections["categorical_associations"] = cat_pairs
        methods_used.append("chi_square")

    # Mixed group comparisons
    mix = _run_group_comparisons(
        df_clean, roles["numeric"], roles["categorical"], spec.max_group_comparisons
    )
    if mix:
        sections["mixed_group_comparisons"] = mix
        methods_used.append("compare_groups_numeric")

    # OLS heuristic (numeric only)
    ols = _run_auto_regression(df_clean, roles["numeric"])
    if ols:
        sections["regression_ols"] = ols
        if "analysis" in ols:
            methods_used.append("ols")

    # Timeseries (optional)
    ts_block: dict[str, Any] | None = None
    if spec.enable_timeseries:
        ts_block = _run_auto_timeseries(df_clean, roles["datetime"], roles["numeric"])
        if ts_block:
            sections["timeseries"] = ts_block
            if "analysis" in ts_block:
                methods_used.append("timeseries")

    # Aggregate hypothesis rows / decision traces from engine outputs.
    hypothesis_rows: list[dict[str, Any]] = []
    decision_steps: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    charts: list[dict[str, Any]] = []

    for pair in cat_pairs:
        analysis = pair.get("analysis", {})
        hypothesis_rows.extend(analysis.get("hypothesis_table") or [])
        steps = (analysis.get("decision_trace") or {}).get("steps") or []
        decision_steps.extend(steps)
        if analysis.get("chart"):
            charts.append(analysis["chart"])
    for m in mix:
        analysis = m.get("analysis", {})
        hypothesis_rows.extend(analysis.get("hypothesis_table") or [])
        steps = (analysis.get("decision_trace") or {}).get("steps") or []
        decision_steps.extend(steps)
    if ols and "analysis" in ols:
        analysis = ols["analysis"]
        hypothesis_rows.extend(analysis.get("hypothesis_table") or [])
        steps = (analysis.get("decision_trace") or {}).get("steps") or []
        decision_steps.extend(steps)
        if analysis.get("diagnostics"):
            diagnostics["ols"] = analysis["diagnostics"]
    if ts_block and "analysis" in ts_block:
        analysis = ts_block["analysis"]
        hypothesis_rows.extend(analysis.get("hypothesis_table") or [])
        if analysis.get("chart"):
            charts.append(analysis["chart"])
        if analysis.get("diagnostics"):
            diagnostics["timeseries"] = analysis["diagnostics"]

    basic = build_basic_analysis(df_clean)
    results_unified: dict[str, Any] = {
        **basic,
        **psycho_mapped,
        "overview": overview,
    }

    academic = _academic_summary(
        roles=roles,
        methods_used=sorted(set(methods_used)),
        cleaning_summary=cleaning_summary,
        hypothesis_rows=hypothesis_rows,
        warnings_in=warnings,
    )

    finished_at = datetime.now(UTC).isoformat()

    # Provenance ref: bao gồm hash file upload (đã tính lúc upload),
    # pip lock hash + engine versions (tính tại đây để cố định snapshot).
    repo_root = infer_repo_root()
    provenance_ref = {
        "manifest_stored_as": raw_job_meta.get("manifest_stored_as"),
        "profiling_engine_version": raw_job_meta.get("profiling_engine_version"),
        "started_at": started_at,
        "cleaned_at": cleaned_at,
        "finished_at": finished_at,
        "random_seed": spec.random_seed,
        "psychometrics_engine": PSYCHO_ENGINE_ID,
        "file_sha256": raw_job_meta.get("file_sha256"),
        "pip_lock_sha256": pip_lock_sha256(repo_root),
        "engine_versions": engine_versions(),
    }

    # Cleaning block cho export_zip_builder (data_clean_preview giới hạn 200 dòng).
    preview_rows = df_clean.head(200).to_dict(orient="records") if not df_clean.empty else []

    return {
        "engine": ENGINE_ID,
        "version": ENGINE_VERSION,
        "spec": spec.model_dump(mode="json"),
        "academic_summary": academic,
        "hypothesis_table": hypothesis_rows,
        "decision_trace": {"steps": decision_steps},
        "diagnostics": diagnostics,
        "evidence": {
            "psychometrics": psycho_parsed.get("results") if psycho_parsed else [],
            "regression": ols,
            "timeseries": ts_block,
        },
        "charts": charts,
        "results": results_unified,
        "analysis_sections": sections,
        "hypothesis_suggestions": {
            "items": suggestions,
            "meta": llm_meta,
        },
        "cleaning": {
            "summary": cleaning_summary,
            "log": cleaning_log,
            "data_clean_preview": preview_rows,
        },
        "profiling": raw_job_meta.get("profiling"),
        "profiling_detail": raw_job_meta.get("profiling_detail"),
        "provenance_ref": provenance_ref,
    }
