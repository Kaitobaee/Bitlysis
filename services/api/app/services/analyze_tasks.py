"""Tác vụ phân tích — Phase 4: thống kê Python + diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import TypeAdapter

from app.config import Settings
from app.schemas.stats import AnalyzeRequest, FullAutoAnalysisSpec, RPipelineSpec, TimeSeriesSpec
from app.services import job_store
from app.services.job_data import load_job_dataframe
from app.services.auto_analysis import run_full_auto_analysis
from app.services.r_pipeline import run_r_pipeline_json
from app.services.stats_engine import build_basic_analysis, run_stats_analysis
from app.services.timeseries_engine import run_timeseries_analysis

logger = logging.getLogger(__name__)


def run_analyze(settings: Settings, job_id: str, spec_payload: dict[str, Any]) -> None:
    try:
        raw = job_store.read_raw_meta(settings, job_id)
        if raw is None:
            logger.warning("analyze: meta missing for job %s", job_id)
            return
        df = load_job_dataframe(settings, raw)
        spec = TypeAdapter(AnalyzeRequest).validate_python(spec_payload)
        if isinstance(spec, TimeSeriesSpec):
            out = run_timeseries_analysis(df, spec)
            basic = build_basic_analysis(df)
            summary = {
                "engine": "python_timeseries",
                "version": 6,
                "spec": spec_payload,
                "decision_trace": out["decision_trace"],
                "hypothesis_table": out["hypothesis_table"],
                "diagnostics": out["diagnostics"],
                "chart": out["chart"],
                "metrics": out["metrics"],
                "warnings": out["warnings"],
                "meta": out["meta"],
                "results": {
                    **basic,
                    "time_series": {
                        "value_column": spec.value_column,
                        "date_column": spec.date_column,
                        "method": spec.method,
                    },
                    "forecast": out.get("chart"),
                    "mape": out.get("metrics", {}).get("mape"),
                    "rmse": out.get("metrics", {}).get("rmse"),
                },
                "profiling": raw.get("profiling"),
            }
            job_store.patch_meta(
                settings,
                job_id,
                {
                    "status": "succeeded",
                    "result_summary": summary,
                    "error": None,
                },
            )
            return

        if isinstance(spec, RPipelineSpec):
            parsed, r_stderr, rc = run_r_pipeline_json(settings, df, spec.analyses)
            basic = build_basic_analysis(df)
            summary = {
                "engine": "bitlysis_r_pipeline",
                "version": 5,
                "spec": spec_payload,
                "r_output": parsed,
                "r_stderr": (r_stderr or "")[:16_000],
                "r_returncode": rc,
                "results": {
                    **basic,
                    **(parsed if isinstance(parsed, dict) else {}),
                },
                "profiling": raw.get("profiling"),
            }
            ok = bool(parsed.get("ok")) and rc == 0
            fail_summary = None if ok else summary
            job_store.patch_meta(
                settings,
                job_id,
                {
                    "status": "succeeded" if ok else "failed",
                    "result_summary": summary if ok else fail_summary,
                    "error": None
                    if ok
                    else {
                        "code": "r_pipeline_failed",
                        "message": str(parsed.get("error", "R pipeline lỗi"))[:2000],
                    },
                },
            )
            return

        if isinstance(spec, FullAutoAnalysisSpec):
            summary = run_full_auto_analysis(settings, df, spec)
            job_store.patch_meta(
                settings,
                job_id,
                {
                    "status": "succeeded",
                    "result_summary": summary,
                    "error": None,
                },
            )
            return

        out = run_stats_analysis(df, spec)
        basic = build_basic_analysis(df)
        selected_method = str(out.get("decision_trace", {}).get("selected_method", ""))
        hypothesis_rows = out.get("hypothesis_table")
        first_row = (
            hypothesis_rows[0]
            if isinstance(hypothesis_rows, list) and hypothesis_rows and isinstance(hypothesis_rows[0], dict)
            else None
        )

        mapped_results: dict[str, Any] = {**basic}
        if selected_method in {"student_t_test", "welch_t_test"} and first_row is not None:
            mapped_results["t_test"] = first_row
        elif selected_method == "mann_whitney_u" and first_row is not None:
            mapped_results["mann_whitney"] = first_row
        elif selected_method == "one_way_anova" and first_row is not None:
            mapped_results["anova"] = first_row
        elif selected_method == "kruskal_wallis" and first_row is not None:
            mapped_results["kruskal_wallis"] = first_row
        elif selected_method == "ols":
            mapped_results["regression"] = {
                "model": "ols",
                "rows": hypothesis_rows,
            }
            diag = out.get("diagnostics", {})
            if isinstance(diag, dict):
                mapped_results["assumptions"] = {
                    "alpha": diag.get("alpha"),
                    "residual": diag.get("residual"),
                }
                mapped_results["vif"] = diag.get("vif")
                mapped_results["qq_plot"] = diag.get("qq_plot")
        elif selected_method == "chi2_independence" and first_row is not None:
            mapped_results["categorical_association"] = first_row

        summary = {
            "engine": "python_stats",
            "version": 4,
            "spec": spec_payload,
            "decision_trace": out["decision_trace"],
            "hypothesis_table": out["hypothesis_table"],
            "diagnostics": out.get("diagnostics", {}),
            "chart": out.get("chart"),
            "results": mapped_results,
            "profiling": raw.get("profiling"),
            "profiling_detail": raw.get("profiling_detail"),
        }
        job_store.patch_meta(
            settings,
            job_id,
            {
                "status": "succeeded",
                "result_summary": summary,
                "error": None,
            },
        )
    except FileNotFoundError:
        logger.warning("analyze: meta missing for job %s", job_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("analyze failed for %s", job_id)
        try:
            job_store.patch_meta(
                settings,
                job_id,
                {
                    "status": "failed",
                    "error": {"code": "analyze_failed", "message": str(e)},
                },
            )
        except FileNotFoundError:
            pass


def run_analyze_stub(settings: Settings, job_id: str) -> None:
    """Giữ tương thích gọi cũ không body — không dùng trong API Phase 4."""

    logger.warning("run_analyze_stub is deprecated; use run_analyze with spec")
    try:
        job_store.patch_meta(
            settings,
            job_id,
            {
                "status": "succeeded",
                "result_summary": {"engine": "stub", "version": 1},
                "error": None,
            },
        )
    except FileNotFoundError:
        pass
