from pydantic import BaseModel, Field

from app.schemas.job import JobStatus
from app.schemas.profiling import ProfilingSummary


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus = Field(default=JobStatus.uploaded, description="Trạng thái job sau upload")
    filename: str = Field(description="Tên file gốc từ client")
    stored_path: str = Field(description="Đường dẫn file đã lưu (relative tới upload_dir)")
    size_bytes: int
    columns: list[str]
    row_preview_count: int = Field(
        description="Số dòng đã profile (cap bởi profiling_max_rows; không phải tổng file nếu lớn)",
    )
    profiling: ProfilingSummary = Field(description="Tóm tắt profiling Phase 3")
    manifest_stored_as: str = Field(description="File run_manifest.json (relative upload_dir)")
