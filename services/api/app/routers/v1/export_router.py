"""Phase 8 — ZIP export: matplotlib/plotly PNG, PDF, docx, Excel; heavy gate."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.schemas.export_phase import ExportStartAccepted
from app.schemas.job import JobStatus
from app.services import job_store
from app.services.export_zip_builder import build_export_zip_bytes
from app.services.export_renderers import render_matplotlib_series_png
from app.services.job_data import load_job_dataframe

router = APIRouter(tags=["export"])


def _export_zip_path(settings: Settings, job_id: str) -> str:
    return f"{job_id}.export.zip"


@router.post(
    "/jobs/{job_id}/export/start",
    response_model=ExportStartAccepted,
    status_code=202,
)
def start_export_phase(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> ExportStartAccepted:
    """Bắt buộc trước khi tải ZIP vượt ngưỡng heavy (ADR Phase 8)."""
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    st = str(raw.get("status", ""))
    if st == JobStatus.exporting.value:
        return ExportStartAccepted(job_id=job_id, status=JobStatus.exporting)
    if st != JobStatus.succeeded.value:
        raise HTTPException(
            status_code=409,
            detail="Chỉ job đã analyze thành công (succeeded) mới bắt đầu export phase.",
        )
    job_store.patch_meta(
        settings,
        job_id,
        {
            "status": JobStatus.exporting.value,
            "export_phase_started_at": datetime.now(UTC).isoformat(),
        },
    )
    return ExportStartAccepted(job_id=job_id, status=JobStatus.exporting)


@router.post("/jobs/{job_id}/export")
def build_and_download_export_zip(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    st = str(raw.get("status", ""))
    if st not in {JobStatus.succeeded.value, JobStatus.exporting.value}:
        raise HTTPException(
            status_code=409,
            detail="Export cần job succeeded hoặc đang exporting (ZIP nặng).",
        )
    try:
        df = load_job_dataframe(settings, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    zip_bytes = build_export_zip_bytes(settings, job_id, raw, df)
    n = len(zip_bytes)
    if n > settings.export_max_zip_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP vượt export_max_zip_bytes ({settings.export_max_zip_bytes}).",
        )
    if n > settings.export_zip_heavy_threshold_bytes and st != JobStatus.exporting.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "heavy_export_requires_export_phase",
                "message": "ZIP lớn — gọi POST /v1/jobs/<id>/export/start rồi thử lại.",
                "threshold_bytes": settings.export_zip_heavy_threshold_bytes,
                "actual_bytes": n,
            },
        )

    rel = _export_zip_path(settings, job_id)
    out = (settings.upload_dir / rel).resolve()
    root = settings.upload_dir.resolve()
    out.relative_to(root)
    out.write_bytes(zip_bytes)

    job_store.patch_meta(
        settings,
        job_id,
        {
            "status": JobStatus.succeeded.value,
            "export_stored_as": rel,
            "export_size_bytes": n,
            "export_built_at": datetime.now(UTC).isoformat(),
        },
    )

    return FileResponse(
        path=str(out),
        filename=f"{job_id}_export.zip",
        media_type="application/zip",
    )


@router.get("/jobs/{job_id}/export/download")
def download_last_export_zip(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    rel = raw.get("export_stored_as")
    if not rel:
        raise HTTPException(status_code=404, detail="Chưa có bản export — gọi POST /export")
    path = (settings.upload_dir / str(rel)).resolve()
    root = settings.upload_dir.resolve()
    path.relative_to(root)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File export không còn trên đĩa")
    return FileResponse(
        path=str(path),
        filename=f"{job_id}_export.zip",
        media_type="application/zip",
    )


@router.get("/jobs/{job_id}/charts/matplotlib")
def preview_matplotlib_chart(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Render chart preview directly for UI (without downloading ZIP)."""
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    try:
        df = load_job_dataframe(settings, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    rel = f"{job_id}.matplotlib_preview.png"
    out = (settings.upload_dir / rel).resolve()
    root = settings.upload_dir.resolve()
    out.relative_to(root)

    ok = render_matplotlib_series_png(df, out)
    if not ok or not out.is_file():
        raise HTTPException(
            status_code=404,
            detail="Không có cột số phù hợp để vẽ biểu đồ matplotlib.",
        )

    return FileResponse(
        path=str(out),
        filename=f"{job_id}_matplotlib_series.png",
        media_type="image/png",
    )
