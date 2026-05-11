"""Phase 8 — Matplotlib/Plotly PNG, PDF bảng, docx, Excel (data_clean + results_raw)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _short_value(value: Any, limit: int = 420) -> str:
    if isinstance(value, dict):
        important_keys = [
            "kind",
            "method",
            "decision",
            "p_value",
            "effect_size",
            "alpha",
            "degrees_of_freedom",
        ]
        compact = {k: value.get(k) for k in important_keys if k in value}
        if not compact:
            compact = value
        txt = json.dumps(compact, ensure_ascii=False)
    elif isinstance(value, list):
        if value and isinstance(value[0], dict):
            txt = json.dumps(value[:3], ensure_ascii=False)
            if len(value) > 3:
                txt += f" ... (+{len(value) - 3} items)"
        else:
            txt = json.dumps(value[:20], ensure_ascii=False)
            if len(value) > 20:
                txt += f" ... (+{len(value) - 20} items)"
    else:
        txt = str(value)
    return txt if len(txt) <= limit else f"{txt[:limit]}..."


def _resolve_pdf_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ]

    for p in candidates:
        if p.is_file():
            pdfmetrics.registerFont(TTFont("BitlysisSans", str(p)))
            normal = "BitlysisSans"
            break
    else:
        normal = "Helvetica"

    for p in bold_candidates:
        if p.is_file():
            pdfmetrics.registerFont(TTFont("BitlysisSansBold", str(p)))
            bold = "BitlysisSansBold"
            break
    else:
        bold = "Helvetica-Bold"

    return normal, bold


def render_matplotlib_series_png(df: pd.DataFrame, out_path: Path) -> bool:
    """Line chart cột số đầu tiên → PNG (Agg)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) < 1:
        return False
    col = num_cols[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.plot(df[col].to_numpy(), marker="o", markersize=2, linewidth=1)
    ax.set_title(f"Chuỗi: {col}")
    ax.set_xlabel("Chỉ số dòng")
    ax.set_ylabel(str(col))
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


def render_plotly_series_png(df: pd.DataFrame, out_path: Path) -> bool:
    """Plotly → PNG (cần kaleido). Lỗi → False, không chặn export."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) < 1:
        return False
    col = num_cols[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=df[col].tolist(),
            mode="lines+markers",
            name=str(col),
            marker=dict(size=4),
        ),
    )
    fig.update_layout(title=f"Plotly: {col}", xaxis_title="Index", yaxis_title=str(col))
    try:
        fig.write_image(str(out_path), width=800, height=500, scale=1)
    except Exception:  # noqa: BLE001
        logger.warning("plotly.write_image failed (kaleido?)")
        return False
    return True


def render_summary_tables_pdf(result_summary: dict[str, Any] | None, out_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[list[Any]] = [["Khóa", "Giá trị (rút gọn)"]]
    if result_summary:
        for k, v in list(result_summary.items())[:50]:
            cell = _short_value(v, limit=520)
            rows.append([str(k), cell])
    else:
        rows.append(["result_summary", "(trống)"])

    doc = SimpleDocTemplate(str(out_path), pagesize=A4)
    story: list[Any] = []
    styles = getSampleStyleSheet()
    normal_font, bold_font = _resolve_pdf_fonts()
    title_style = ParagraphStyle(
        "BitlysisTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=18,
        leading=22,
    )
    cell_style = ParagraphStyle(
        "BitlysisCell",
        parent=styles["BodyText"],
        fontName=normal_font,
        fontSize=8,
        leading=10,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "BitlysisHeader",
        parent=styles["BodyText"],
        fontName=bold_font,
        fontSize=8,
        textColor=colors.whitesmoke,
    )

    story.append(Paragraph("Bitlysis - Tom tat ket qua (bang)", title_style))
    story.append(Spacer(1, 12))

    table_rows: list[list[Any]] = []
    for i, (k, v) in enumerate(rows):
        if i == 0:
            table_rows.append([
                Paragraph(str(k), header_style),
                Paragraph(str(v), header_style),
            ])
        else:
            table_rows.append([
                Paragraph(str(k), cell_style),
                Paragraph(str(v), cell_style),
            ])

    t = Table(table_rows, colWidths=[125, 370], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), normal_font),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ],
        ),
    )
    story.append(t)
    doc.build(story)


def _add_kv_paragraph(doc: Any, key: str, value: Any) -> None:
    from docx.shared import Pt

    p = doc.add_paragraph()
    run_k = p.add_run(f"{key}: ")
    run_k.bold = True
    run_k.font.size = Pt(11)
    run_v = p.add_run(str(value))
    run_v.font.size = Pt(11)


def _add_hypothesis_table(doc: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        doc.add_paragraph("(Chưa có giả thuyết nào được kiểm định.)")
        return
    headers = ["ID", "Phương pháp", "Statistic", "p-value", "Effect", "Quyết định"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
    for r in rows[:50]:
        cells = table.add_row().cells
        cells[0].text = str(r.get("hypothesis_id", ""))
        cells[1].text = str(r.get("method", ""))
        stat = r.get("statistic")
        cells[2].text = f"{stat:.4f}" if isinstance(stat, (int, float)) else "—"
        p_val = r.get("p_value")
        cells[3].text = f"{p_val:.4f}" if isinstance(p_val, (int, float)) else "—"
        es = r.get("effect_size")
        es_kind = r.get("effect_size_kind") or ""
        if isinstance(es, (int, float)):
            cells[4].text = f"{es:.3f} ({es_kind})" if es_kind else f"{es:.3f}"
        else:
            cells[4].text = "—"
        decision = str(r.get("decision", ""))
        cells[5].text = {
            "reject_h0": "Bác bỏ H0",
            "fail_to_reject_h0": "Không đủ bằng chứng",
            "not_applicable": "Không áp dụng",
        }.get(decision, decision)


def render_docx_report(
    *,
    job_id: str,
    original_filename: str,
    columns: list[str],
    result_summary: dict[str, Any] | None,
    out_path: Path,
    template_path: Path | None,
) -> None:
    """Báo cáo Word học thuật từ `result_summary` (orchestrator unified schema).

    Nếu `template_path` trỏ tới file .docx hợp lệ, dùng làm khuôn (giữ
    style/cover page); ngược lại tạo Document trống và build từ đầu.
    """
    from docx import Document

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if template_path is not None and template_path.is_file():
        doc = Document(str(template_path))
    else:
        doc = Document()

    rs = result_summary or {}
    eng = str(rs.get("engine") or "unknown_engine")
    version = rs.get("version", "?")

    doc.add_heading("Bitlysis — Báo cáo phân tích thống kê", level=0)
    _add_kv_paragraph(doc, "Job ID", job_id)
    _add_kv_paragraph(doc, "Tệp gốc", original_filename)
    _add_kv_paragraph(doc, "Số cột", len(columns))
    _add_kv_paragraph(doc, "Engine", f"{eng} (version {version})")

    # 1. Tóm tắt học thuật
    academic = rs.get("academic_summary") if isinstance(rs, dict) else None
    if isinstance(academic, dict):
        doc.add_heading("1. Tóm tắt học thuật", level=1)
        _add_kv_paragraph(doc, "Loại dữ liệu", academic.get("data_type", "—"))
        methods = academic.get("methods") or []
        if methods:
            _add_kv_paragraph(doc, "Phương pháp", ", ".join(methods))
        if academic.get("rationale"):
            doc.add_paragraph(academic["rationale"])
        assumptions = academic.get("assumptions") or []
        if assumptions:
            doc.add_paragraph("Giả định đã áp dụng:")
            for a in assumptions:
                doc.add_paragraph(str(a), style="List Bullet")
        if academic.get("conclusion"):
            doc.add_heading("Kết luận", level=2)
            doc.add_paragraph(str(academic["conclusion"]))
        warns = academic.get("warnings") or []
        if warns:
            doc.add_heading("Cảnh báo", level=2)
            for w in warns:
                doc.add_paragraph(str(w), style="List Bullet")

    # 2. Bảng giả thuyết
    rows = rs.get("hypothesis_table") if isinstance(rs, dict) else None
    if isinstance(rows, list):
        doc.add_heading("2. Bảng giả thuyết", level=1)
        _add_hypothesis_table(doc, rows)

    # 3. Cleaning log
    cleaning = rs.get("cleaning") if isinstance(rs, dict) else None
    if isinstance(cleaning, dict):
        doc.add_heading("3. Làm sạch dữ liệu", level=1)
        summary = cleaning.get("summary") or {}
        _add_kv_paragraph(doc, "Số dòng trước", summary.get("rows_before", "—"))
        _add_kv_paragraph(doc, "Số dòng sau", summary.get("rows_after", "—"))
        _add_kv_paragraph(doc, "Chính sách missing", summary.get("missing_policy", "—"))
        _add_kv_paragraph(doc, "Chính sách outlier", summary.get("outlier_policy", "—"))
        for entry in (cleaning.get("log") or [])[:30]:
            action = entry.get("action", "")
            detail = entry.get("detail", "")
            doc.add_paragraph(f"• {action}: {detail}", style="List Bullet")

    # 4. Minh bạch học thuật (provenance)
    prov = rs.get("provenance_ref") if isinstance(rs, dict) else None
    if isinstance(prov, dict):
        doc.add_heading("4. Minh bạch học thuật", level=1)
        _add_kv_paragraph(doc, "Engine psychometrics", prov.get("psychometrics_engine", "—"))
        _add_kv_paragraph(doc, "SHA-256 file gốc", prov.get("file_sha256") or "—")
        _add_kv_paragraph(doc, "pip lock hash", prov.get("pip_lock_sha256") or "—")
        seed_val = prov.get("random_seed")
        _add_kv_paragraph(doc, "Random seed", seed_val if seed_val is not None else "—")
        for ts_key in ("started_at", "cleaned_at", "finished_at"):
            v = prov.get(ts_key)
            if v:
                _add_kv_paragraph(doc, f"Timestamp ({ts_key})", v)
        ev = prov.get("engine_versions") or {}
        if ev:
            doc.add_paragraph("Phiên bản thư viện:")
            for name, ver in ev.items():
                doc.add_paragraph(f"• {name} = {ver}", style="List Bullet")

    # 5. Danh sách cột (rút gọn)
    doc.add_heading("5. Danh sách cột", level=1)
    doc.add_paragraph(", ".join(columns[:80]) or "(không có)")

    doc.save(str(out_path))


def render_workbook_clean_and_raw(
    df: pd.DataFrame,
    result_summary: dict[str, Any] | None,
    out_path: Path,
    *,
    max_rows: int,
    df_clean: pd.DataFrame | None = None,
    cleaning_log: list[dict[str, Any]] | None = None,
) -> None:
    """Xuất Excel: `data_raw`, `data_clean`, `cleaning_log`, `results_raw`.

    Khi `df_clean` không truyền (legacy caller), sheet `data_clean` sẽ là bản
    sao `df.head(max_rows)` để giữ tương thích test cũ.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_sample = df.head(max_rows)
    clean_sample = (df_clean if df_clean is not None else df).head(max_rows)

    raw_rows: list[list[str]] = []
    if result_summary:
        for k, v in result_summary.items():
            raw_rows.append([str(k), json.dumps(v, ensure_ascii=False)])
    else:
        raw_rows.append(["result_summary", "null"])
    raw_df = pd.DataFrame(raw_rows, columns=["key", "value_json"])

    log_rows: list[dict[str, Any]] = []
    for entry in cleaning_log or []:
        log_rows.append({
            "action": str(entry.get("action", "")),
            "detail": str(entry.get("detail", "")),
            "evidence_json": json.dumps(entry.get("evidence") or {}, ensure_ascii=False),
        })
    empty_log_row = {
        "action": "(empty)",
        "detail": "Không có bước cleaning",
        "evidence_json": "{}",
    }
    log_df = pd.DataFrame(log_rows) if log_rows else pd.DataFrame([empty_log_row])

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        clean_sample.to_excel(writer, sheet_name="data_clean", index=False)
        raw_sample.to_excel(writer, sheet_name="data_raw", index=False)
        log_df.to_excel(writer, sheet_name="cleaning_log", index=False)
        raw_df.to_excel(writer, sheet_name="results_raw", index=False)
