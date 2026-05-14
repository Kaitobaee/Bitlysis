from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query

from app.config import Settings, get_settings
from app.jobs import get_queue
from app.repositories import get_job_repository
from app.schemas.job import (
    AnalyzeAccepted,
    FileAnalysisChatRequest,
    FileAnalysisChatResponse,
    JobDetail,
    JobStatus,
    RQueuedAccepted,
)
from app.schemas.stats import AnalyzeRequest
from app.services.file_chat import answer_file_job_question
from app.services.job_data import load_job_dataframe

router = APIRouter(tags=["jobs"])


def _column_chart_payload(
    df: pd.DataFrame,
    column: str,
    chart_type: str,
    max_items: int,
) -> dict[str, object]:
    if column not in df.columns:
        raise ValueError("Cột không tồn tại trong dữ liệu")

    s = df[column].dropna()
    if s.empty:
        raise ValueError("Cột không có dữ liệu hợp lệ")

    if pd.api.types.is_numeric_dtype(s):
        s_num = pd.to_numeric(s, errors="coerce").dropna()
        if s_num.empty:
            raise ValueError("Không thể đọc dữ liệu số từ cột")
        if int(s_num.nunique()) > max_items:
            bins = min(10, max(4, int(s_num.nunique() ** 0.5)))
            binned = pd.cut(s_num.astype(float), bins=bins, duplicates="drop")
            counts = binned.value_counts().sort_index()
            labels = [str(idx) for idx in counts.index]
            values = [int(v) for v in counts.values]
        else:
            counts = s_num.round(2).astype(str).value_counts().head(max_items)
            labels = [str(idx) for idx in counts.index]
            values = [int(v) for v in counts.values]
    else:
        counts = s.astype(str).value_counts().head(max_items)
        labels = [str(idx) for idx in counts.index]
        values = [int(v) for v in counts.values]

    return {
        "kind": chart_type,
        "title": f"{chart_type.upper()} - {column}",
        "column": column,
        "labels": labels,
        "values": values,
        "total": int(sum(values)),
    }


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    detail = await get_job_repository(settings).get_job_detail(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return detail


@router.get("/jobs/{job_id}/charts/quick")
async def get_quick_chart(
    job_id: str,
    column: str = Query(..., min_length=1),
    chart_type: str = Query("bar", pattern="^(bar|pie|line|area|donut)$"),
    max_items: int = Query(12, ge=3, le=30),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    raw = await get_job_repository(settings).get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    try:
        df = await load_job_dataframe(settings, raw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Không đọc được dữ liệu job: {e}") from e

    try:
        return _column_chart_payload(df, column, chart_type, max_items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/chat", response_model=FileAnalysisChatResponse)
async def chat_file_analysis(
    job_id: str,
    payload: FileAnalysisChatRequest,
    settings: Settings = Depends(get_settings),
) -> FileAnalysisChatResponse:
    raw = await get_job_repository(settings).get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")

    try:
        df = await load_job_dataframe(settings, raw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Khong doc duoc du lieu job: {e}") from e

    try:
        return await asyncio.to_thread(
            answer_file_job_question,
            settings,
            raw_job=raw,
            dataframe=df,
            question=payload.question,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/jobs/{job_id}/analyze",
    status_code=202,
    response_model=AnalyzeAccepted,
)
async def start_analyze(
    job_id: str,
    background_tasks: BackgroundTasks,
    spec: AnalyzeRequest,
    settings: Settings = Depends(get_settings),
) -> AnalyzeAccepted:
    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    st = str(raw.get("status", ""))
    allowed = {JobStatus.uploaded.value, JobStatus.failed.value}
    if st not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Job không thể chạy analyze ở trạng thái: {st}",
        )
    spec_dump = spec.model_dump(mode="json")
    await repo.patch_job(
        job_id,
        {
            "status": JobStatus.analyzing.value,
            "error": None,
            "analysis_spec": spec_dump,
        },
    )
    await get_queue(settings, background_tasks).enqueue(job_id, "analyze", {"spec": spec_dump})
    return AnalyzeAccepted(job_id=job_id, status=JobStatus.analyzing)


@router.post(
    "/jobs/{job_id}/r-queue",
    status_code=202,
    response_model=RQueuedAccepted,
    summary="Queue job for R pipeline processing via GitHub Actions",
)
async def queue_for_r_pipeline(
    job_id: str,
    settings: Settings = Depends(get_settings),
    x_run_token: str | None = Header(default=None),
) -> RQueuedAccepted:
    """Chuyển job vào hàng đợi R pipeline.

    Có thể gọi sau khi Python analyze xong (để bổ sung psychometrics bằng R)
    hoặc thay thế cho Python analyze khi cần kết quả R thuần túy.
    Bảo vệ bởi X-Run-Token nếu token được cấu hình.
    """
    required_token = (settings.run_endpoint_token or "").strip()
    if required_token and x_run_token != required_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    st = str(raw.get("status", ""))
    # Cho phép queue từ: uploaded, analyzing (vừa chạy Python xong), succeeded, failed
    queueable = {
        JobStatus.uploaded.value,
        JobStatus.analyzing.value,
        JobStatus.succeeded.value,
        JobStatus.failed.value,
    }
    if st not in queueable:
        raise HTTPException(
            status_code=409,
            detail=f"Không thể queue R pipeline từ trạng thái: {st}",
        )

    now = datetime.now(UTC).isoformat()
    await repo.patch_job(job_id, {
        "status": JobStatus.r_queued.value,
        "r_queued_at": now,
        "status_updated_at": now,
        "error": None,
    })
    return RQueuedAccepted(job_id=job_id)


@router.get(
    "/jobs/r-queue",
    summary="[GitHub Actions] List jobs pending R pipeline processing",
    description=(
        "Trả danh sách job đang ở trạng thái r_queued. "
        "Bảo vệ bởi X-Run-Token. Chỉ dành cho GitHub Actions cron."
    ),
)
async def list_r_queued_jobs(
    limit: int = Query(default=10, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    x_run_token: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    required_token = (settings.run_endpoint_token or "").strip()
    if required_token and x_run_token != required_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    repo = get_job_repository(settings)
    all_jobs = await repo.list_jobs()
    r_queued = [
        j for j in all_jobs
        if str(j.get("status", "")) == JobStatus.r_queued.value
    ]
    # Sắp xếp theo thời gian queue sớm nhất trước
    r_queued.sort(key=lambda j: str(j.get("r_queued_at") or j.get("uploaded_at") or ""))

    results = []
    for job in r_queued[:limit]:
        results.append({
            "job_id": job.get("job_id"),
            "stored_as": job.get("stored_as"),
            "columns": job.get("columns", []),
            "r_queued_at": job.get("r_queued_at"),
            "analysis_spec": job.get("analysis_spec"),
        })
    return results


@router.delete("/jobs/{job_id}", status_code=204)
async def remove_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> None:
    if not await get_job_repository(settings).delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job không tồn tại")
