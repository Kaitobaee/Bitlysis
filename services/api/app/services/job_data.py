"""Đọc DataFrame từ file job upload (dùng chung analyze + export)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.config import Settings


def load_job_dataframe(settings: Settings, raw: dict[str, Any]) -> pd.DataFrame:
    name = raw.get("stored_as")
    if not name:
        msg = "Job meta missing stored_as"
        raise ValueError(msg)
    path = (settings.upload_dir / str(name)).resolve()
    upload_root = settings.upload_dir.resolve()
    path.relative_to(upload_root)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        with pd.ExcelFile(path, engine="openpyxl") as xl:
            return pd.read_excel(xl, sheet_name=0)
    msg = f"Unsupported file type for dataframe load: {suffix}"
    raise ValueError(msg)
