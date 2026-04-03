"""Xóa job/upload quá hạn theo ADR 0003."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.services import job_store

logger = logging.getLogger(__name__)


def sweep_expired_jobs(settings: Settings) -> int:
    if not settings.retention_enabled:
        return 0
    upload_dir = settings.upload_dir
    if not upload_dir.is_dir():
        return 0

    cutoff = datetime.now(UTC) - timedelta(hours=settings.retention_hours)
    deleted = 0
    for meta_file in upload_dir.glob("*.meta.json"):
        try:
            raw = json.loads(meta_file.read_text(encoding="utf-8"))
            uploaded_str = raw.get("uploaded_at")
            if not uploaded_str:
                continue
            uploaded = datetime.fromisoformat(uploaded_str.replace("Z", "+00:00"))
            if uploaded.tzinfo is None:
                uploaded = uploaded.replace(tzinfo=UTC)
            if uploaded < cutoff:
                job_id = str(raw["job_id"])
                if job_store.delete_job(settings, job_id):
                    deleted += 1
        except (json.JSONDecodeError, KeyError, ValueError):
            _delete_orphan_meta(meta_file, upload_dir)
            continue
    return deleted


def _delete_orphan_meta(meta_file: Path, _upload_dir: Path) -> None:
    """Meta hỏng: xóa file .meta để tránh tích lũy."""
    try:
        meta_file.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete corrupt meta %s", meta_file)

