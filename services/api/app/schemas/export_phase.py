"""Phase 8 — export ZIP."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobStatus


class ExportStartAccepted(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.exporting
    message: str = Field(
        default="Job chuyển sang exporting — gọi POST /export để tải ZIP nặng.",
    )
