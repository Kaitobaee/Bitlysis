from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.schemas.job import JobStatus
from app.schemas.profiling import ProfilingSummary
from app.services.file_magic import validate_saved_file_magic
from app.services.profiling import profile_file
from app.services.provenance import build_run_manifest, write_manifest

ALLOWED_SUFFIXES = frozenset({".csv", ".xlsx", ".xlsm"})
PROFILING_ENGINE_VERSION = 1


@dataclass
class StoredUpload:
    job_id: str
    original_filename: str
    stored_path: str
    absolute_path: Path
    size_bytes: int
    columns: list[str]
    row_preview_count: int
    profiling: ProfilingSummary
    manifest_stored_as: str


def _safe_basename(name: str | None) -> str:
    if not name or not str(name).strip():
        return "upload"
    base = Path(name).name
    base = re.sub(r"[^\w.\- ]+", "_", base, flags=re.UNICODE).strip()
    return base[:180] if base else "upload"


def _suffix_from_name(filename: str) -> str:
    return Path(filename).suffix.lower()


async def save_and_validate_upload(
    file: UploadFile,
    settings: Settings,
) -> StoredUpload:
    original = _safe_basename(file.filename)
    suffix = _suffix_from_name(original)
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ chấp nhận .csv, .xlsx, .xlsm. Đuôi nhận được: {suffix or '(none)'}",
        )

    job_id = str(uuid.uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{job_id}{suffix}"
    dest = (settings.upload_dir / dest_name).resolve()

    try:
        dest.relative_to(settings.upload_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid upload path") from None

    size = 0
    chunk_size = 1024 * 1024
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File vượt quá giới hạn {settings.max_upload_bytes} bytes",
                    )
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except OSError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Lưu file thất bại: {e}") from e

    try:
        validate_saved_file_magic(dest, suffix)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise

    try:
        prof = profile_file(dest, suffix, settings.profiling_max_rows)
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Không đọc được dữ liệu (file hỏng, sai định dạng, hoặc encoding).",
        ) from None

    ts = datetime.now(UTC).isoformat()
    manifest_rel = f"{job_id}.manifest.json"
    manifest_abs = settings.upload_dir / manifest_rel
    manifest_body = build_run_manifest(job_id, PROFILING_ENGINE_VERSION)
    manifest_body["profiling_sample"] = {
        "row_count_profiled": prof.row_count_in_profile,
        "profiled_row_cap": prof.profiled_row_cap,
        "column_count": len(prof.columns),
        "encoding_used": prof.encoding_used,
        "sheet_used": prof.sheet_used,
        "transformations": prof.transformations,
    }
    write_manifest(manifest_abs, manifest_body)

    summary = ProfilingSummary(
        engine_version=PROFILING_ENGINE_VERSION,
        row_count_profiled=prof.row_count_in_profile,
        profiled_row_cap=prof.profiled_row_cap,
        encoding_used=prof.encoding_used,
        sheet_used=prof.sheet_used,
        sheet_names=prof.sheet_names,
        duplicate_row_count_sample=prof.duplicate_row_count,
        column_count=len(prof.columns),
        transformations=prof.transformations,
    )

    meta = {
        "job_id": job_id,
        "original_filename": original,
        "stored_as": dest_name,
        "size_bytes": size,
        "content_type": file.content_type,
        "uploaded_at": ts,
        "status": JobStatus.uploaded.value,
        "status_updated_at": ts,
        "columns": prof.columns,
        "row_preview_count": prof.row_count_in_profile,
        "error": None,
        "result_summary": None,
        "profiling": summary.model_dump(),
        "profiling_detail": {
            "column_profiles": prof.column_profiles,
        },
        "manifest_stored_as": manifest_rel,
        "profiling_engine_version": PROFILING_ENGINE_VERSION,
        "profiled_at": ts,
    }
    meta_path = settings.upload_dir / f"{job_id}.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    rel = dest_name
    return StoredUpload(
        job_id=job_id,
        original_filename=original,
        stored_path=rel,
        absolute_path=dest,
        size_bytes=size,
        columns=prof.columns,
        row_preview_count=prof.row_count_in_profile,
        profiling=summary,
        manifest_stored_as=manifest_rel,
    )
