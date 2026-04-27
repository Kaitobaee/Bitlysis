"""Backward-compatible wrappers for analysis jobs.

New orchestration lives in `app.core.analysis` so API routes and queue adapters
do not depend on compute details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings
from app.core.analysis import run_analysis_job
from app.repositories import get_job_repository


def run_analyze_stub(settings: Settings, job_id: str) -> None:
    """Giữ tương thích gọi cũ không body — không dùng trong API Phase 4."""

    logger.warning("run_analyze_stub is deprecated; use run_analyze with spec")
    try:
        repo = get_job_repository(settings)
        asyncio.run(
            repo.patch_job(
                job_id,
                {
                    "status": "succeeded",
                    "result_summary": {"engine": "stub", "version": 1},
                    "error": None,
                },
            )
        )
    except FileNotFoundError:
        pass


logger = logging.getLogger(__name__)


def run_analyze(settings: Settings, job_id: str, spec_payload: dict[str, Any]) -> None:
    logger.warning("run_analyze is deprecated; queue app.core.analysis.run_analysis_job instead")
    asyncio.run(run_analysis_job(settings, job_id, spec_payload))
