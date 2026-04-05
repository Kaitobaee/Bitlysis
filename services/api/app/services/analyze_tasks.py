"""Tác vụ phân tích — Phase 4: thống kê Python + diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import TypeAdapter

from app.config import Settings
from app.schemas.stats import AnalyzeRequest, RPipelineSpec, TimeSeriesSpec
from app.services import job_store
from app.services.job_data import load_job_dataframe
from app.services.r_pipeline import run_r_pipeline_json
from app.services.stats_engine import run_stats_analysis
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
            summary = {
                "engine": "bitlysis_r_pipeline",
                "version": 5,
                "spec": spec_payload,
                "r_output": parsed,
                "r_stderr": (r_stderr or "")[:16_000],
                "r_returncode": rc,
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

        out = run_stats_analysis(df, spec)
        summary = {
            "engine": "python_stats",
            "version": 4,
            "spec": spec_payload,
            "decision_trace": out["decision_trace"],
            "hypothesis_table": out["hypothesis_table"],
            "diagnostics": out.get("diagnostics", {}),
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
