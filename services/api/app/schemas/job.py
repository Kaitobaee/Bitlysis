from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    uploaded = "uploaded"
    profiling = "profiling"
    analyzing = "analyzing"
    exporting = "exporting"
    succeeded = "succeeded"
    failed = "failed"


class JobError(BaseModel):
    code: str = "job_error"
    message: str


class JobDetail(BaseModel):
    job_id: str
    status: JobStatus
    filename: str
    stored_path: str
    size_bytes: int
    columns: list[str]
    row_preview_count: int
    uploaded_at: str | None = None
    status_updated_at: str | None = None
    error: JobError | None = None
    result_summary: dict[str, Any] | None = Field(
        default=None,
        description="Tóm tắt kết quả (stub hoặc sau phân tích thật)",
    )


class AnalyzeAccepted(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.analyzing
    message: str = Field(
        default="Accepted. Poll GET /v1/jobs/<job_id> for status.",
    )
