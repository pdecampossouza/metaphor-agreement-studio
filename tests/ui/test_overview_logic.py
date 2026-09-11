from pathlib import Path

from metaphor_agreement_studio.ui.pages.overview import overview_candidates


def test_overview_candidates_scan_workspace_and_imports(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    imports.mkdir()
    (tmp_path / "Eduardo.xlsx").write_bytes(b"candidate")
    (imports / "Sofia.xlsm").write_bytes(b"candidate")

    found = overview_candidates(tmp_path)

    assert [candidate.display_name for candidate in found] == ["Eduardo.xlsx", "Sofia.xlsm"]
