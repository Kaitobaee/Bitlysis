from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.schemas.job import JobStatus
from app.services.file_magic import validate_saved_file_magic

ALLOWED_SUFFIXES = frozenset({".csv", ".xlsx", ".xlsm"})
READ_PREVIEW_ROWS = 200


@dataclass
class StoredUpload:
    job_id: str
    original_filename: str
    stored_path: str
    absolute_path: Path
    size_bytes: int
    columns: list[str]
    row_preview_count: int


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

    columns: list[str]
    preview_rows: int
    try:
        columns, preview_rows = _read_preview(dest, suffix)
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Không đọc được dữ liệu (file hỏng, sai định dạng, hoặc encoding).",
        ) from None

    ts = datetime.now(UTC).isoformat()
    meta = {
        "job_id": job_id,
        "original_filename": original,
        "stored_as": dest_name,
        "size_bytes": size,
        "content_type": file.content_type,
        "uploaded_at": ts,
        "status": JobStatus.uploaded.value,
        "status_updated_at": ts,
        "columns": columns,
        "row_preview_count": preview_rows,
        "error": None,
        "result_summary": None,
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
        columns=columns,
        row_preview_count=preview_rows,
    )


def _read_preview(path: Path, suffix: str) -> tuple[list[str], int]:
    if suffix == ".csv":
        last_err: Exception | None = None
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(
                    path,
                    nrows=READ_PREVIEW_ROWS,
                    encoding=encoding,
                    low_memory=False,
                )
                cols = [str(c) for c in df.columns.tolist()]
                return cols, len(df.index)
            except Exception as e:  # noqa: BLE001 - gom lỗi đọc file
                last_err = e
        raise last_err or RuntimeError("csv read failed")
    if suffix in {".xlsx", ".xlsm"}:
        df = pd.read_excel(path, nrows=READ_PREVIEW_ROWS, engine="openpyxl")
        cols = [str(c) for c in df.columns.tolist()]
        return cols, len(df.index)
    raise ValueError(f"unsupported suffix {suffix}")
