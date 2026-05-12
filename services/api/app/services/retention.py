"""Xóa job/upload quá hạn theo ADR 0003."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.repositories.job_repository import FileJobRepository

logger = logging.getLogger(__name__)


async def sweep_expired_jobs(settings: Settings) -> int:
    if not settings.retention_enabled:
        return 0

    cutoff = datetime.now(UTC) - timedelta(hours=settings.retention_hours)
    deleted = 0
    repo = FileJobRepository(settings)
    for raw in await repo.iter_jobs():
        try:
            uploaded_str = raw.get("uploaded_at")
            if not uploaded_str:
                continue
            uploaded = datetime.fromisoformat(uploaded_str.replace("Z", "+00:00"))
            if uploaded.tzinfo is None:
                uploaded = uploaded.replace(tzinfo=UTC)
            if uploaded < cutoff:
                job_id = str(raw["job_id"])
                if await repo.delete_job(job_id):
                    deleted += 1
        except (KeyError, ValueError):
            continue
    return deleted

