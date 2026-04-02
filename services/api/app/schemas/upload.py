from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    job_id: str
    filename: str = Field(description="Tên file gốc từ client")
    stored_path: str = Field(description="Đường dẫn file đã lưu (relative tới upload_dir)")
    size_bytes: int
    columns: list[str]
    row_preview_count: int = Field(
        description="Số dòng dữ liệu đã đọc để xác thực (không phải tổng số dòng file)",
    )
