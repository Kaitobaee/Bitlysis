"""Kiểm tra magic bytes sau khi file đã lưu (khớp đuôi + nội dung thật)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

READ_HEAD = 8192


def validate_saved_file_magic(path: Path, suffix: str) -> None:
    if not path.is_file():
        raise HTTPException(status_code=500, detail="File upload không tồn tại sau khi ghi")
    size = path.stat().st_size
    if size == 0:
        raise HTTPException(status_code=400, detail="File rỗng")
    head = path.read_bytes()[:READ_HEAD]

    if suffix in {".xlsx", ".xlsm"}:
        if not head.startswith(b"PK"):
            raise HTTPException(
                status_code=415,
                detail="Nội dung không phải Office Open XML (.xlsx mở đầu bằng ZIP PK).",
            )
    elif suffix == ".csv":
        if b"\x00" in head:
            raise HTTPException(
                status_code=415,
                detail="CSV chứa byte null — có thể là file nhị phân, không phải văn bản.",
            )
