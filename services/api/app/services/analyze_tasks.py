"""Tác vụ phân tích chạy nền (stub Phase 1 — thay bằng pipeline thật sau)."""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.services import job_store

logger = logging.getLogger(__name__)


def run_analyze_stub(settings: Settings, job_id: str) -> None:
    try:
        time.sleep(0.02)
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
        logger.warning("analyze stub: meta missing for job %s", job_id)
    except Exception as e:  # noqa: BLE001 - ghi lỗi job
        logger.exception("analyze stub failed for %s", job_id)
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
