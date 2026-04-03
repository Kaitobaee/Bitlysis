"""Tác vụ phân tích — Phase 4: thống kê Python + diagnostics."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from pydantic import TypeAdapter

from app.config import Settings
from app.schemas.stats import AnalyzeRequest
from app.services import job_store
from app.services.stats_engine import run_stats_analysis

logger = logging.getLogger(__name__)


def _load_job_dataframe(settings: Settings, raw: dict[str, Any]) -> pd.DataFrame:
    name = raw.get("stored_as")
    if not name:
        msg = "Job meta missing stored_as"
        raise ValueError(msg)
    path = (settings.upload_dir / str(name)).resolve()
    upload_root = settings.upload_dir.resolve()
    path.relative_to(upload_root)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        with pd.ExcelFile(path, engine="openpyxl") as xl:
            return pd.read_excel(xl, sheet_name=0)
    msg = f"Unsupported file type for analysis: {suffix}"
    raise ValueError(msg)


def run_analyze(settings: Settings, job_id: str, spec_payload: dict[str, Any]) -> None:
    try:
        raw = job_store.read_raw_meta(settings, job_id)
        if raw is None:
            logger.warning("analyze: meta missing for job %s", job_id)
            return
        df = _load_job_dataframe(settings, raw)
        spec = TypeAdapter(AnalyzeRequest).validate_python(spec_payload)
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
