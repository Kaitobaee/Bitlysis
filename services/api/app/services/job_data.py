"""Đọc DataFrame từ file job upload (dùng chung analyze + export)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.config import Settings
from app.storage import get_storage


async def load_job_dataframe(settings: Settings, raw: dict[str, Any]) -> pd.DataFrame:
    name = raw.get("stored_as")
    if not name:
        msg = "Job meta missing stored_as"
        raise ValueError(msg)
    key = str(name)
    suffix = "." + key.rsplit(".", 1)[-1].lower() if "." in key else ""
    content = await get_storage(settings).read_file(key)
    if suffix == ".csv":
        from io import BytesIO

        return pd.read_csv(BytesIO(content))
    if suffix in {".xlsx", ".xlsm"}:
        from io import BytesIO

        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as xl:
            return pd.read_excel(xl, sheet_name=0)
    msg = f"Unsupported file type for dataframe load: {suffix}"
    raise ValueError(msg)
