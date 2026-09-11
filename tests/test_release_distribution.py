from __future__ import annotations

from pathlib import Path

import metaphor_agreement_studio


ROOT = Path(__file__).resolve().parents[1]


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8", errors="replace")


def test_release_metadata_is_1_0_0_and_documented() -> None:
    assert metaphor_agreement_studio.__version__ == "1.0.0"
    pyproject = _text("pyproject.toml")
    assert 'version = "1.0.0"' in pyproject
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()
    assert (ROOT / "RELEASE_CHECKLIST.md").is_file()
    assert "1.0.0" in _text("CHANGELOG.md")


def test_windows_release_launchers_are_one_click_and_share_release_requirements() -> None:
    assert (ROOT / "requirements-release.txt").is_file()
    assert (ROOT / "requirements-dev-release.txt").is_file()
    start = _text("START_METAPHOR_STUDIO_WINDOWS.bat")
    stop = _text("STOP_METAPHOR_STUDIO_WINDOWS.bat")
    tests = _text("RUN_RELEASE_TESTS_WINDOWS.bat")
    assert "requirements-release.txt" in start
    assert "Metaphor Agreement Studio - Release 1.0" in start
    assert ".mas_streamlit.port" in start
    assert ".mas_streamlit.port" in stop
    assert "requirements-dev-release.txt" in tests
    assert "pytest" in tests and "ruff" in tests


def test_macos_release_has_clickable_app_and_command_fallbacks() -> None:
    start = ROOT / "START_METAPHOR_STUDIO_MAC.command"
    stop = ROOT / "STOP_METAPHOR_STUDIO_MAC.command"
    app = ROOT / "Metaphor Agreement Studio.app"
    executable = app / "Contents" / "MacOS" / "MetaphorAgreementStudio"
    plist = app / "Contents" / "Info.plist"
    assert start.is_file()
    assert stop.is_file()
    assert executable.is_file()
    assert plist.is_file()
    start_text = start.read_text(encoding="utf-8")
    assert "requirements-release.txt" in start_text
    assert "--background" in start_text
    assert "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" in start_text
    assert "/opt/homebrew/bin/python3.12" in start_text
    assert "START_METAPHOR_STUDIO_MAC.command" in executable.read_text(encoding="utf-8")
    assert "Metaphor Agreement Studio" in plist.read_text(encoding="utf-8")


def test_release_docs_explain_windows_mac_privacy_and_reference_modes() -> None:
    readme = _text("README.md")
    required_phrases = (
        "Quick Analysis",
        "Research Project",
        "No reference",
        "Reference rater",
        "Expert benchmark",
        "original workbook is never modified",
        "Windows",
        "macOS",
        "START_METAPHOR_STUDIO_WINDOWS.bat",
        "Metaphor Agreement Studio.app",
        "uv sync",
        "uv run streamlit run app.py",
    )
    for phrase in required_phrases:
        assert phrase in readme


def test_release_ui_contains_no_future_phase_placeholder_copy() -> None:
    ui_root = ROOT / "src" / "metaphor_agreement_studio" / "ui"
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in ui_root.rglob("*.py")
    )
    assert "becomes available in the next implementation phase" not in combined


def test_release_launchers_upgrade_existing_env_for_comparison_pdf_dependency() -> None:
    requirements = _text("requirements-release.txt")
    windows = _text("START_METAPHOR_STUDIO_WINDOWS.bat")
    mac = _text("START_METAPHOR_STUDIO_MAC.command")

    assert "reportlab" in requirements
    assert "reportlab" in windows
    assert "reportlab" in mac
