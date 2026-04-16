from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Payload tối giản để gọi trực tiếp R core engine."""

    records: list[dict[str, Any]] = Field(
        min_length=1,
        description="Dữ liệu bảng dạng list object để chuyển thành DataFrame",
    )
    analyses: list[dict[str, Any]] = Field(
        min_length=1,
        description='Danh sách phân tích R, ví dụ {"type":"cronbach_alpha",...}',
    )


class RunResponse(BaseModel):
    ok: bool
    engine: str = "bitlysis_r_pipeline"
    r_returncode: int
    result: dict[str, Any]
    stderr: str | None = None
