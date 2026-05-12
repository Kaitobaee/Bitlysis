"""Phase 8 — export ZIP."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobStatus


class ExportStartAccepted(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.exporting
    message: str = Field(
        default=(
            "Job chuyển sang exporting và đã enqueue export. "
            "Poll GET /jobs/<id> hoặc tải lại khi export_stored_as xuất hiện."
        ),
    )
