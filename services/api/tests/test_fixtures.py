"""Đảm bảo fixtures tồn tại (Phase 0 quality gate)."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

EXPECTED = (
    "sample_utf8.csv",
    "sample_cp1252.csv",
    "sample_clean.xlsx",
    "sample_multi_sheet_merged.xlsx",
)


def test_fixtures_exist():
    for name in EXPECTED:
        path = FIXTURES / name
        assert path.is_file(), f"Missing fixture: {path.relative_to(FIXTURES.parent)}"
