from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class ProfilingResult:
    columns: list[str]
    row_count_in_profile: int
    profiled_row_cap: int
    column_profiles: list[dict]
    transformations: list[dict] = field(default_factory=list)
    duplicate_row_count: int | None = None
    encoding_used: str | None = None
    sheet_used: str | None = None
    sheet_names: list[str] | None = None


def _log(transformations: list[dict], action: str, **details: object) -> None:
    extra = {k: v for k, v in details.items() if v is not None}
    transformations.append({"action": action, **extra})


def _profile_dataframe(df: pd.DataFrame, transformations: list[dict]) -> list[dict]:
    profiles: list[dict] = []
    n = len(df.index)
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        miss_pct = round(100.0 * missing / n, 4) if n else 0.0
        nu = int(s.nunique(dropna=True))
        is_const = nu <= 1
        profiles.append(
            {
                "name": str(col),
                "pandas_dtype": str(s.dtype),
                "missing_count": missing,
                "missing_pct": miss_pct,
                "nunique": nu,
                "is_constant": is_const,
            },
        )
    return profiles


def _duplicate_header_note(path: Path, encoding: str, transformations: list[dict]) -> None:
    try:
        with path.open(encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
    except (OSError, StopIteration, UnicodeDecodeError):
        return
    if len(header) != len(set(header)):
        _log(
            transformations,
            "duplicate_header_labels",
            note="Header có nhãn trùng; pandas có thể đổi tên cột (.1, .2).",
            header_sample=header[:20],
        )


def profile_csv(path: Path, max_rows: int) -> ProfilingResult:
    transformations: list[dict] = []
    last_err: Exception | None = None
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            _duplicate_header_note(path, encoding, transformations)
            df = pd.read_csv(
                path,
                nrows=max_rows,
                encoding=encoding,
                low_memory=False,
            )
            _normalize_strings(df, transformations)
            dup_ct = int(df.duplicated().sum()) if len(df) else 0
            profiles = _profile_dataframe(df, transformations)
            cols = [str(c) for c in df.columns.tolist()]
            return ProfilingResult(
                columns=cols,
                row_count_in_profile=len(df.index),
                profiled_row_cap=max_rows,
                column_profiles=profiles,
                transformations=transformations,
                duplicate_row_count=dup_ct,
                encoding_used=encoding,
            )
        except Exception as e:  # noqa: BLE001
            last_err = e
            transformations.clear()
    raise last_err or RuntimeError("csv profile failed")


def _normalize_strings(df: pd.DataFrame, transformations: list[dict]) -> None:
    changed_cols: list[str] = []
    for c in df.columns:
        if df[c].dtype != object:
            continue
        series = df[c]

        def _trim_one(v: object) -> object:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return v
            if isinstance(v, str):
                t = v.strip()
                return t if t != v else v
            return v

        new = series.map(_trim_one)
        if not new.equals(series):
            changed_cols.append(str(c))
        df[c] = new
    if changed_cols:
        _log(
            transformations,
            "trim_whitespace_object_columns",
            columns=changed_cols[:80],
        )


def profile_excel(path: Path, max_rows: int) -> ProfilingResult:
    transformations: list[dict] = []
    with pd.ExcelFile(path, engine="openpyxl") as xl:
        sheet_names = list(xl.sheet_names)
        sheet = sheet_names[0]
        _log(transformations, "excel_sheet_selected", sheet=sheet, available_sheets=sheet_names)
        df = pd.read_excel(xl, sheet_name=sheet, nrows=max_rows)
        _normalize_strings(df, transformations)
        dup_ct = int(df.duplicated().sum()) if len(df) else 0
        profiles = _profile_dataframe(df, transformations)
        cols = [str(c) for c in df.columns.tolist()]
        unnamed = [c for c in cols if str(c).startswith("Unnamed")]
        if unnamed:
            _log(
                transformations,
                "unnamed_columns_detected",
                columns=unnamed[:15],
                hint="Có thể do merged cells hoặc header sai dòng.",
            )
        return ProfilingResult(
            columns=cols,
            row_count_in_profile=len(df.index),
            profiled_row_cap=max_rows,
            column_profiles=profiles,
            transformations=transformations,
            duplicate_row_count=dup_ct,
            sheet_used=sheet,
            sheet_names=sheet_names,
        )


def profile_file(path: Path, suffix: str, max_rows: int) -> ProfilingResult:
    if suffix == ".csv":
        return profile_csv(path, max_rows)
    if suffix in {".xlsx", ".xlsm"}:
        return profile_excel(path, max_rows)
    msg = f"unsupported suffix: {suffix}"
    raise ValueError(msg)
