from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.content_extractor import extract_text_from_bytes

router = APIRouter(tags=["content"])

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


class ContentExtractResponse(BaseModel):
    text: str
    filename: str
    char_count: int


@router.post("/content/extract", response_model=ContentExtractResponse)
async def extract_content_file(file: UploadFile) -> ContentExtractResponse:
    raw = await file.read()
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 10 MB).")

    filename = file.filename or "upload"

    try:
        text = extract_text_from_bytes(filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Không thể đọc file: {exc}") from exc

    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="File không có nội dung văn bản có thể trích xuất.")

    return ContentExtractResponse(text=text, filename=filename, char_count=len(text))
