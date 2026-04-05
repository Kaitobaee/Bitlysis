"""Đọc/ghi job metadata trên filesystem ({job_id}.meta.json)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.schemas.job import JobDetail, JobError, JobStatus
from app.schemas.profiling import ProfilingSummary


def meta_path(settings: Settings, job_id: str) -> Path:
    return settings.upload_dir / f"{job_id}.meta.json"


def read_raw_meta(settings: Settings, job_id: str) -> dict[str, Any] | None:
    path = meta_path(settings, job_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def patch_meta(
    settings: Settings,
    job_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    path = meta_path(settings, job_id)
    if not path.is_file():
        msg = f"Job meta not found: {job_id}"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates)
    data["status_updated_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def raw_to_job_detail(raw: dict[str, Any]) -> JobDetail:
    err = raw.get("error")
    error_model = JobError(**err) if isinstance(err, dict) and "message" in err else None
    raw_status = str(raw.get("status", JobStatus.uploaded.value))
    try:
        status = JobStatus(raw_status)
    except ValueError:
        status = JobStatus.uploaded
    prof = None
    if isinstance(raw.get("profiling"), dict):
        try:
            prof = ProfilingSummary.model_validate(raw["profiling"])
        except ValidationError:
            prof = None
    a_spec = raw.get("analysis_spec")
    return JobDetail(
        job_id=str(raw["job_id"]),
        status=status,
        filename=str(raw.get("original_filename", "")),
        stored_path=str(raw.get("stored_as", "")),
        size_bytes=int(raw.get("size_bytes", 0)),
        columns=list(raw.get("columns") or []),
        row_preview_count=int(raw.get("row_preview_count", 0)),
        uploaded_at=raw.get("uploaded_at"),
        status_updated_at=raw.get("status_updated_at"),
        error=error_model,
        result_summary=raw.get("result_summary"),
        profiling=prof,
        manifest_stored_as=raw.get("manifest_stored_as"),
        profiling_detail=raw.get("profiling_detail"),
        analysis_spec=a_spec if isinstance(a_spec, dict) else None,
        export_stored_as=raw.get("export_stored_as"),
    )


def get_job_detail(settings: Settings, job_id: str) -> JobDetail | None:
    raw = read_raw_meta(settings, job_id)
    if raw is None:
        return None
    return raw_to_job_detail(raw)


def delete_job(settings: Settings, job_id: str) -> bool:
    """Xóa file dữ liệu + meta. Trả False nếu không có meta."""
    raw = read_raw_meta(settings, job_id)
    if raw is None:
        return False
    upload_root = settings.upload_dir.resolve()
    for key in ("stored_as", "manifest_stored_as", "export_stored_as"):
        name = raw.get(key)
        if not name:
            continue
        p = (upload_root / str(name)).resolve()
        try:
            p.relative_to(upload_root)
        except ValueError:
            meta_path(settings, job_id).unlink(missing_ok=True)
            return True
        p.unlink(missing_ok=True)
    meta_path(settings, job_id).unlink(missing_ok=True)
    return True
