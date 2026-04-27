"""Phase 8 — ZIP export: matplotlib/plotly PNG, PDF, docx, Excel; heavy gate."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.config import Settings, get_settings
from app.core.export import (
    ExportFileNotFoundError,
    ExportJobNotFoundError,
    ExportJobStateError,
    ExportTooLargeError,
    HeavyExportRequiresStartError,
    build_and_store_export,
    mark_exporting,
    read_stored_export,
    render_matplotlib_preview_bytes,
)
from app.jobs import get_queue
from app.schemas.export_phase import ExportStartAccepted
from app.schemas.job import JobStatus

router = APIRouter(tags=["export"])


@router.post(
    "/jobs/{job_id}/export/start",
    response_model=ExportStartAccepted,
    status_code=202,
)
async def start_export_phase(
    job_id: str,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> ExportStartAccepted:
    """Bắt buộc trước khi tải ZIP vượt ngưỡng heavy (ADR Phase 8)."""
    try:
        await mark_exporting(settings, job_id)
    except ExportJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    except ExportJobStateError as e:
        raise HTTPException(
            status_code=409,
            detail=e.message,
        ) from e
    await get_queue(settings, background_tasks).enqueue(job_id, "export")
    return ExportStartAccepted(job_id=job_id, status=JobStatus.exporting)


@router.post("/jobs/{job_id}/export")
async def build_and_download_export_zip(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        zip_bytes = await build_and_store_export(settings, job_id, enforce_heavy_gate=True)
    except ExportJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    except ExportJobStateError as e:
        raise HTTPException(
            status_code=409,
            detail=e.message,
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ExportTooLargeError as e:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP vượt export_max_zip_bytes ({e.max_bytes}).",
        ) from e
    except HeavyExportRequiresStartError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "heavy_export_requires_export_phase",
                "message": "ZIP lớn — gọi POST /v1/jobs/<id>/export/start rồi thử lại.",
                "threshold_bytes": e.threshold_bytes,
                "actual_bytes": e.actual_bytes,
            },
        ) from e

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_export.zip"'},
    )


@router.get("/jobs/{job_id}/export/download")
async def download_last_export_zip(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        content = await read_stored_export(settings, job_id)
    except ExportJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    except ExportFileNotFoundError:
        raise HTTPException(status_code=404, detail="Chưa có bản export — gọi POST /export")
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_export.zip"'},
    )


@router.get("/jobs/{job_id}/charts/matplotlib")
async def preview_matplotlib_chart(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    """Render chart preview directly for UI (without downloading ZIP)."""
    try:
        content = await render_matplotlib_preview_bytes(settings, job_id)
    except ExportJobNotFoundError:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ExportFileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Không có cột số phù hợp để vẽ biểu đồ matplotlib.",
        )

    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{job_id}_matplotlib_series.png"'},
    )
