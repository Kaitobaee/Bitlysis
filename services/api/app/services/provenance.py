"""run_manifest.json — phiên bản runtime & reproducibility.

Phase 5 refactor:
- Bỏ phụ thuộc R/`renv.lock`; thay bằng `pip_lock_sha256` (hash của
  `pyproject.toml`).
- Thêm `file_sha256` cho file upload gốc (tạo ngay tại `upload_store`).
- Thêm `engine_versions` chi tiết (pandas, numpy, scipy, statsmodels, …) +
  `psychometrics_engine` id/version.
- Hỗ trợ timestamp per-phase (`upload`, `profile`, `clean`, `analyze`, `export`).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def _pkg_ver(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def file_sha256(path: Path) -> str | None:
    """SHA-256 (hex) của file; trả prefix 'sha256:' để khớp định dạng cũ."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    except OSError:
        return None


def pip_lock_sha256(repo_root: Path | None) -> str | None:
    """Hash `pyproject.toml` (thay `renv.lock` cũ)."""
    if repo_root is None:
        return None
    candidates = [
        repo_root / "services" / "api" / "pyproject.toml",
        repo_root / "pyproject.toml",
    ]
    for p in candidates:
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            return f"sha256:{h}"
    return None


def renv_lock_sha256(repo_root: Path | None) -> str | None:
    """Legacy alias: trả None (không còn R). Giữ cho code/test cũ không gãy."""
    _ = repo_root
    return None


def infer_repo_root() -> Path | None:
    """Tìm root monorepo Bitlysis (chứa `services/api`)."""
    here = Path(__file__).resolve()
    for base in (Path.cwd(), *here.parents):
        if (base / "services" / "api").is_dir():
            return base
    return None


def engine_versions() -> dict[str, str]:
    """Phiên bản các thư viện chính ảnh hưởng kết quả thống kê."""
    pkgs = {}
    for name in (
        "pandas",
        "numpy",
        "scipy",
        "statsmodels",
        "openpyxl",
        "matplotlib",
        "plotly",
        "reportlab",
        "python-docx",
    ):
        v = _pkg_ver(name)
        if v is not None:
            pkgs[name] = v
    return pkgs


def build_run_manifest(
    job_id: str,
    profiling_engine_version: int,
    repo_root: Path | None = None,
    *,
    file_hash: str | None = None,
    random_seed: int | None = None,
) -> dict[str, Any]:
    root = repo_root or infer_repo_root()
    pkgs = engine_versions()
    return {
        "schema_version": 2,
        "job_id": job_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "profiling_engine_version": profiling_engine_version,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": pkgs,
        },
        "psychometrics_engine": {
            "id": "bitlysis_python_psychometrics",
            "version": 1,
        },
        "pip_lock_sha256": pip_lock_sha256(root),
        # Giữ key cũ để client legacy không gãy; giá trị luôn None.
        "renv_lock_sha256": None,
        "source_file": {
            "sha256": file_hash,
        },
        "random_seed": random_seed,
        "phase_timestamps": {
            "manifest_built_at": datetime.now(UTC).isoformat(),
        },
    }


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_manifest_with_export(base: dict[str, Any]) -> dict[str, Any]:
    """Nhúng metadata export ZIP vào run_manifest (bản copy trong ZIP)."""
    import copy

    m = copy.deepcopy(base)
    export_pkgs: dict[str, str] = {}
    for label, dist_name in (
        ("matplotlib", "matplotlib"),
        ("plotly", "plotly"),
        ("kaleido", "kaleido"),
        ("reportlab", "reportlab"),
        ("python-docx", "python-docx"),
        ("openpyxl", "openpyxl"),
        ("pandas", "pandas"),
    ):
        v = _pkg_ver(dist_name)
        if v is not None:
            export_pkgs[label] = v
    m["export"] = {
        "phase": 8,
        "package_versions": export_pkgs,
        "zip_layout": [
            "run_manifest.json",
            "docs/charts/matplotlib_series.png",
            "docs/charts/plotly_series.png",
            "docs/tables/summary_tables.pdf",
            "docs/report.docx",
            "docs/data/workbook.xlsx",
        ],
        "exported_at": datetime.now(UTC).isoformat(),
    }
    return m
