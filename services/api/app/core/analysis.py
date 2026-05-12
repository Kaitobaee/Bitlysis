"""Analysis job orchestration, decoupled from FastAPI routes."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import TypeAdapter

from app.config import Settings
from app.repositories import get_job_repository
from app.schemas.stats import (
    AnalyzeRequest,
    ComprehensiveAnalysisSpec,
    FullAutoAnalysisSpec,
    PsychometricsSpec,
    TimeSeriesSpec,
)
from app.services.auto_analysis import run_full_auto_analysis
from app.services.job_data import load_job_dataframe
from app.services.psychometrics import ENGINE_ID as PSYCHO_ENGINE_ID
from app.services.psychometrics import run_psychometrics
from app.services.stats_engine import build_basic_analysis, run_stats_analysis
from app.services.timeseries_engine import run_timeseries_analysis

logger = logging.getLogger(__name__)


def _map_psychometrics_results(parsed: dict[str, Any]) -> dict[str, Any]:
    """Map output dispatcher psychometrics → key shape mà UI ResultSummary mong đợi.

    Trả về dict gồm `cronbach`, `efa`, `pls_sem` (mỗi cái là list các result block
    cùng type), kèm các alias `factor_loadings`, `htmt`, `path_coefficients`,
    `r2`, `q2`, `f2`, `bootstrapping`, `fornell_larcker`, `measurement_model`,
    `structural_model` để mở rộng UI sau này không cần đổi backend.
    """
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
        typ = block.get("type")
        if typ == "cronbach_alpha":
            cronbach.append(block)
        elif typ == "efa":
            efa.append(block)
        elif typ == "pls_sem":
            pls.append(block)

    if cronbach:
        out["cronbach"] = cronbach
    if efa:
        out["efa"] = efa
        first_efa = next((b for b in efa if b.get("ran")), efa[0])
        if first_efa.get("loadings"):
            out["factor_loadings"] = first_efa["loadings"]
        if first_efa.get("communalities"):
            out["communalities"] = first_efa["communalities"]
        if first_efa.get("variance_proportion"):
            out["variance_explained"] = first_efa["variance_proportion"]
        if first_efa.get("eigenvalues"):
            out["eigenvalues"] = first_efa["eigenvalues"]
        if first_efa.get("scree_plot"):
            out["scree_plot"] = first_efa["scree_plot"]
        if first_efa.get("kmo_bartlett"):
            out["kmo_bartlett"] = first_efa["kmo_bartlett"]
        if first_efa.get("factor_correlation_matrix"):
            out["factor_correlation_matrix"] = first_efa["factor_correlation_matrix"]
    if pls:
        out["pls_sem"] = pls
        first_pls = next((b for b in pls if b.get("ran")), pls[0])
        if first_pls.get("measurement_model"):
            out["measurement_model"] = first_pls["measurement_model"]
        if first_pls.get("structural_model"):
            out["structural_model"] = first_pls["structural_model"]
            paths = first_pls["structural_model"].get("path_coefficients")
            if paths:
                out["path_coefficients"] = paths
            r2 = first_pls["structural_model"].get("r_squared")
            if r2:
                out["r2"] = r2
            q2 = first_pls["structural_model"].get("q_squared")
            if q2:
                out["q2"] = q2
            f2 = first_pls["structural_model"].get("f_squared")
            if f2:
                out["f2"] = f2
        if first_pls.get("htmt"):
            out["htmt"] = first_pls["htmt"]
        if first_pls.get("fornell_larcker"):
            out["fornell_larcker"] = first_pls["fornell_larcker"]
        if first_pls.get("bootstrapping"):
            out["bootstrapping"] = first_pls["bootstrapping"]

    return out


async def run_analysis_job(settings: Settings, job_id: str, spec_payload: dict[str, Any]) -> None:
    repo = get_job_repository(settings)
    try:
        raw = await repo.get_job(job_id)
        if raw is None:
            logger.warning("analyze: meta missing for job %s", job_id)
            return
        df = await load_job_dataframe(settings, raw)
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
            await repo.patch_job(
                job_id,
                {
                    "status": "succeeded",
                    "result_summary": summary,
                    "error": None,
                },
            )
            return

        if isinstance(spec, PsychometricsSpec):
            seed = getattr(spec, "random_seed", None)
            parsed = run_psychometrics(df, spec.analyses, random_seed=seed)
            basic = build_basic_analysis(df)
            ok = bool(parsed.get("ok"))
            mapped = _map_psychometrics_results(parsed)
            summary = {
                "engine": PSYCHO_ENGINE_ID,
                "version": 6,
                "spec": spec_payload,
                "psychometrics_output": parsed,
                "r_output": parsed,  # alias backward-compat
                "r_stderr": "",
                "r_returncode": 0 if ok else 1,
                "results": {
                    **basic,
                    **mapped,
                },
                "profiling": raw.get("profiling"),
            }
            await repo.patch_job(
                job_id,
                {
                    "status": "succeeded" if ok else "failed",
                    "result_summary": summary if ok else None,
                    "error": None
                    if ok
                    else {
                        "code": "psychometrics_failed",
                        "message": str(parsed.get("error", "Psychometrics lỗi"))[:2000],
                    },
                },
            )
            return

        if isinstance(spec, FullAutoAnalysisSpec):
            summary = run_full_auto_analysis(settings, df, spec)
            await repo.patch_job(
                job_id,
                {
                    "status": "succeeded",
                    "result_summary": summary,
                    "error": None,
                },
            )
            return

        if isinstance(spec, ComprehensiveAnalysisSpec):
            from app.services.orchestrator import run_comprehensive_analysis

            summary = await run_comprehensive_analysis(settings, raw, df, spec)
            await repo.patch_job(
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
        has_first_row = (
            isinstance(hypothesis_rows, list)
            and bool(hypothesis_rows)
            and isinstance(hypothesis_rows[0], dict)
        )
        first_row = (
            hypothesis_rows[0]
            if has_first_row
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
        await repo.patch_job(
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
            await repo.patch_job(
                job_id,
                {
                    "status": "failed",
                    "error": {"code": "analyze_failed", "message": str(e)},
                },
            )
        except FileNotFoundError:
            pass
