"""Endpoint nhận kết quả R pipeline từ GitHub Actions cron.

POST /v1/jobs/{job_id}/r-result
- Được gọi bởi GitHub Actions sau khi Rscript chạy xong
- Bảo vệ bởi X-Run-Token header
- Merge kết quả R vào job (result_summary) và chuyển status → succeeded / failed
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.repositories import get_job_repository
from app.schemas.job import JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["r-pipeline"])


class RResultPayload(BaseModel):
    """Payload mà GitHub Actions POST về sau khi Rscript chạy xong."""

    ok: bool = Field(description="True nếu Rscript thành công")
    engine: str = Field(default="bitlysis_r_pipeline")
    returncode: int = Field(default=0)
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = Field(default=None)
    stderr: str | None = Field(default=None, description="Stderr (tối đa 8 KB)")
    analyses_run: list[str] = Field(
        default_factory=list,
        description="Danh sách analysis type đã chạy (cronbach_alpha, efa, pls_sem, …)",
    )


class RResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    merged: bool


def _require_run_token(
    x_run_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Kiểm tra X-Run-Token — bắt buộc khi run_endpoint_token được cấu hình."""
    required = (settings.run_endpoint_token or "").strip()
    if required and x_run_token != required:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Run-Token")


@router.post(
    "/jobs/{job_id}/r-result",
    response_model=RResultResponse,
    summary="[GitHub Actions] POST R pipeline result back to job",
    description=(
        "Chỉ dành cho GitHub Actions cron workflow. "
        "Sau khi Rscript chạy xong, cron POST kết quả về đây để merge vào job."
    ),
)
async def post_r_result(
    job_id: str,
    payload: RResultPayload,
    settings: Settings = Depends(get_settings),
    _token: None = Depends(_require_run_token),
) -> RResultResponse:
    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    current_status = str(raw.get("status", ""))
    # Chỉ chấp nhận khi job đang ở trạng thái r_queued hoặc r_processing
    allowed_statuses = {JobStatus.r_queued.value, JobStatus.r_processing.value}
    if current_status not in allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Job không thể nhận r-result ở trạng thái: {current_status}",
        )

    now = datetime.now(UTC).isoformat()

    # Chuẩn bị r_block để merge vào result_summary
    r_block = {
        "available": payload.ok and payload.returncode == 0,
        "preferred": True,
        "returncode": payload.returncode,
        "engine": payload.engine,
        "stderr": (payload.stderr or "")[:8000],
        "results": payload.results,
        "error": None if payload.ok else (payload.error or "Rscript failed"),
        "processed_at": now,
        "analyses_run": payload.analyses_run,
    }

    # Merge vào result_summary hiện tại (nếu có từ Python analyze)
    existing_summary: dict[str, Any] = raw.get("result_summary") or {}
    existing_summary["r_block"] = r_block
    existing_summary["psychometrics_block"] = r_block
    existing_summary["r_engine"] = payload.engine
    existing_summary["r_returncode"] = payload.returncode

    new_status = JobStatus.succeeded if payload.ok else JobStatus.failed
    patch: dict[str, Any] = {
        "status": new_status.value,
        "status_updated_at": now,
        "result_summary": existing_summary,
        "r_engine": payload.engine,
        "r_queued_at": raw.get("r_queued_at"),
    }
    if not payload.ok:
        patch["error"] = {
            "code": "r_pipeline_failed",
            "message": payload.error or "Rscript returned non-zero exit code",
        }
    else:
        patch["error"] = None

    await repo.patch_job(job_id, patch)
    logger.info(
        "r_result_received",
        extra={"job_id": job_id, "ok": payload.ok, "engine": payload.engine},
    )

    return RResultResponse(job_id=job_id, status=new_status, merged=True)


@router.post(
    "/jobs/{job_id}/r-processing",
    status_code=204,
    summary="[GitHub Actions] Mark job as r_processing",
    description="GitHub Actions gọi ngay khi bắt đầu chạy Rscript để cập nhật status.",
)
async def mark_r_processing(
    job_id: str,
    settings: Settings = Depends(get_settings),
    _token: None = Depends(_require_run_token),
) -> None:
    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if str(raw.get("status", "")) != JobStatus.r_queued.value:
        raise HTTPException(
            status_code=409,
            detail="Job không ở trạng thái r_queued",
        )
    await repo.patch_job(job_id, {
        "status": JobStatus.r_processing.value,
        "status_updated_at": datetime.now(UTC).isoformat(),
    })
