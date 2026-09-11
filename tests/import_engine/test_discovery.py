from pathlib import Path

from metaphor_agreement_studio.import_engine.discovery import discover_workbooks


def test_discovery_finds_xlsx_and_xlsm_without_opening_them(tmp_path: Path) -> None:
    (tmp_path / "Eduardo.xlsx").write_bytes(b"not-opened")
    imports = tmp_path / "imports"
    imports.mkdir()
    (imports / "Sofia.xlsm").write_bytes(b"not-opened")
    (imports / "~$Sofia.xlsx").write_bytes(b"temp")
    (tmp_path / "notes.csv").write_text("x")

    found = discover_workbooks((tmp_path, imports))

    assert [item.display_name for item in found] == ["Eduardo.xlsx", "Sofia.xlsm"]


def test_discovery_deduplicates_same_file_across_overlapping_roots(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    imports.mkdir()
    (imports / "Eduardo.xlsx").write_bytes(b"same")

    found = discover_workbooks((tmp_path, imports, imports))

    assert [item.display_name for item in found] == ["Eduardo.xlsx"]
