from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Payload tối giản để gọi trực tiếp psychometrics core engine."""

    records: list[dict[str, Any]] = Field(
        min_length=1,
        description="Dữ liệu bảng dạng list object để chuyển thành DataFrame",
    )
    analyses: list[dict[str, Any]] = Field(
        min_length=1,
        description='Danh sách phân tích, ví dụ {"type":"cronbach_alpha",...}',
    )
    random_seed: int | None = Field(
        default=None,
        description="Seed bootstrap PLS-SEM; null = không cố định",
    )


class RunResponse(BaseModel):
    ok: bool
    engine: str = "bitlysis_python_psychometrics"
    r_returncode: int = Field(default=0, description="Backward compat: 0 ok, !=0 lỗi")
    result: dict[str, Any]
    stderr: str | None = None
