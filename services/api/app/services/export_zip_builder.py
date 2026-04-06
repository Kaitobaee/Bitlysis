"""Phase 8 — đóng gói ZIP cấu trúc docs/ + run_manifest.json."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

from app.config import Settings
from app.services.export_renderers import (
    render_docx_report,
    render_matplotlib_series_png,
    render_plotly_series_png,
    render_summary_tables_pdf,
    render_workbook_clean_and_raw,
)
from app.services.provenance import build_run_manifest, merge_manifest_with_export, write_manifest


def _placeholder_png(path: Path, message: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.0, 2.5))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=10)
    fig.savefig(path, dpi=100)
    plt.close(fig)


def _load_base_manifest(settings: Settings, raw: dict[str, Any], job_id: str) -> dict[str, Any]:
    rel = raw.get("manifest_stored_as")
    if rel:
        p = (settings.upload_dir / str(rel)).resolve()
        root = settings.upload_dir.resolve()
        p.relative_to(root)
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    ver = int(raw.get("profiling_engine_version", 1))
    return build_run_manifest(job_id, ver)


def build_export_zip_bytes(
    settings: Settings,
    job_id: str,
    raw: dict[str, Any],
    df: pd.DataFrame,
) -> bytes:
    """Tạo ZIP trong thư mục tạm; trả bytes (để kiểm tra heavy threshold)."""
    base_manifest = _load_base_manifest(settings, raw, job_id)
    merged = merge_manifest_with_export(base_manifest)
    cols = list(raw.get("columns") or [])
    result_summary = (
        raw.get("result_summary")
        if isinstance(raw.get("result_summary"), dict)
        else None
    )
    orig_name = str(raw.get("original_filename", "upload"))

    with TemporaryDirectory() as td:
        stage = Path(td) / "export_root"
        (stage / "docs/charts").mkdir(parents=True)
        (stage / "docs/tables").mkdir(parents=True)
        (stage / "docs/data").mkdir(parents=True)

        m_path = stage / "run_manifest.json"
        write_manifest(m_path, merged)

        mpl_path = stage / "docs/charts/matplotlib_series.png"
        if not render_matplotlib_series_png(df, mpl_path):
            _placeholder_png(mpl_path, "Không có cột số — không vẽ được series.")
        if settings.export_include_plotly:
            render_plotly_series_png(df, stage / "docs/charts/plotly_series.png")
        render_summary_tables_pdf(result_summary, stage / "docs/tables/summary_tables.pdf")
        render_docx_report(
            job_id=job_id,
            original_filename=orig_name,
            columns=cols,
            result_summary=result_summary,
            out_path=stage / "docs/report.docx",
            template_path=settings.export_docx_template_path,
        )
        render_workbook_clean_and_raw(
            df,
            result_summary,
            stage / "docs/data/workbook.xlsx",
            max_rows=settings.export_data_max_rows,
        )

        bio = BytesIO()
        with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in stage.rglob("*"):
                if path.is_file():
                    arc = path.relative_to(stage).as_posix()
                    zf.write(path, arcname=arc)
        return bio.getvalue()
