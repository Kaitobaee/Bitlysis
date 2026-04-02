from fastapi import APIRouter, Depends, File, UploadFile

from app.config import Settings, get_settings
from app.schemas.upload import UploadResponse
from app.services.upload_store import save_and_validate_upload

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="File .csv hoặc .xlsx / .xlsm"),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    stored = await save_and_validate_upload(file, settings)
    return UploadResponse(
        job_id=stored.job_id,
        filename=stored.original_filename,
        stored_path=stored.stored_path,
        size_bytes=stored.size_bytes,
        columns=stored.columns,
        row_preview_count=stored.row_preview_count,
    )
