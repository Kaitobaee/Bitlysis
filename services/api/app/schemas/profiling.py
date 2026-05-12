from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    pandas_dtype: str
    missing_count: int
    missing_pct: float = Field(ge=0.0, le=100.0)
    nunique: int
    is_constant: bool


class ProfilingSummary(BaseModel):
    """Tóm tắt cho API/meta (đầy đủ nằm trong manifest + meta['profiling'])."""

    engine_version: int = 1
    row_count_profiled: int
    profiled_row_cap: int
    encoding_used: str | None = None
    sheet_used: str | None = None
    sheet_names: list[str] | None = None
    duplicate_row_count_sample: int | None = Field(
        default=None,
        description="Số dòng trùng trong mẫu đã profile (không phải toàn file nếu file lớn)",
    )
    column_count: int
    transformations: list[dict] = Field(default_factory=list)
