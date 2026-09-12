from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def test_app_opens_in_english_and_explains_detected_source(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "Teste de Concordancia - Revisor Eduardo.xlsx").write_bytes(b"candidate")
    monkeypatch.setenv("MAS_WORKSPACE", str(tmp_path))

    app_path = Path(__file__).resolve().parents[2] / "app.py"
    at = AppTest.from_file(str(app_path)).run()

    all_markdown = "\n".join(item.value for item in at.markdown)
    assert "Metaphor Agreement Studio" in all_markdown
    assert "Source workbook detected" in all_markdown
    assert any("Inspect & Validate" in button.label for button in at.button)
    assert not at.exception
