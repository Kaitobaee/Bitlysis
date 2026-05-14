from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.profiling import ProfilingSummary


class JobStatus(StrEnum):
    uploaded = "uploaded"
    profiling = "profiling"
    analyzing = "analyzing"
    # R pipeline statuses — jobs được GitHub Actions cron xử lý bằng Rscript
    r_queued = "r_queued"        # Đang chờ GitHub Actions cron pick up
    r_processing = "r_processing"  # GitHub Actions đang chạy Rscript
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
    profiling: ProfilingSummary | None = Field(
        default=None,
        description="Tóm tắt profiling Phase 3 (chi tiết cột trong meta)",
    )
    manifest_stored_as: str | None = Field(
        default=None,
        description="Tên file run_manifest.json trong upload_dir",
    )
    profiling_detail: dict[str, Any] | None = Field(
        default=None,
        description="Chi tiết profiling (column_profiles, …) — có thể lớn",
    )
    analysis_spec: dict[str, Any] | None = Field(
        default=None,
        description="Spec JSON đã gửi khi POST analyze (Phase 4)",
    )
    export_stored_as: str | None = Field(
        default=None,
        description="Tên file ZIP export trong upload_dir (Phase 8)",
    )
    r_queued_at: str | None = Field(
        default=None,
        description="Thời điểm job được đưa vào hàng đợi R (r_queued status)",
    )
    r_engine: str | None = Field(
        default=None,
        description="Engine R đã xử lý job (bitlysis_r_pipeline hoặc None)",
    )


class AnalyzeAccepted(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.analyzing
    message: str = Field(
        default="Accepted. Poll GET /v1/jobs/<job_id> for status.",
    )


class RQueuedAccepted(BaseModel):
    """Response khi job được đưa vào hàng đợi R pipeline."""
    job_id: str
    status: JobStatus = JobStatus.r_queued
    message: str = Field(
        default=(
            "Job queued for R pipeline processing. "
            "GitHub Actions cron will pick up within 15 minutes."
        ),
    )


class FileAnalysisChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: Literal["vi", "en"] = "vi"


class FileAnalysisChatResponse(BaseModel):
    question: str
    answer: str
    job_id: str
    focus: str
