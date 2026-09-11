from __future__ import annotations

from pathlib import Path

import pytest

from metaphor_agreement_studio.common.errors import (
    AnalysisUnavailable,
    ExportError,
    ProjectOpenError,
    UnsupportedWorkbookError,
    ValidationBlocked,
    WorkbookReadError,
)
from metaphor_agreement_studio.common.logging import sanitize_log_context
from metaphor_agreement_studio.ui.error_boundary import describe_user_error, technical_details


@pytest.mark.parametrize(
    ("exc", "expected_phrase"),
    [
        (WorkbookReadError("openpyxl exploded at /secret/path"), "workbook could not be read"),
        (UnsupportedWorkbookError("ValueError: bad extension"), "workbook format is not supported"),
        (ValidationBlocked("KeyError: decision"), "validation still needs your attention"),
        (AnalysisUnavailable("numpy traceback"), "analysis is not available yet"),
        (ProjectOpenError("sqlite3.DatabaseError"), "project could not be opened"),
        (ExportError("PermissionError C:/Users/Name"), "export could not be created"),
    ],
)
def test_known_application_errors_use_safe_research_copy(exc: Exception, expected_phrase: str) -> None:
    copy = describe_user_error(exc)
    rendered = f"{copy.title} {copy.message} {copy.action}".casefold()
    assert expected_phrase in rendered
    for forbidden in ("valueerror", "keyerror", "traceback", "openpyxl", "sqlite3", "/secret/path"):
        assert forbidden not in rendered


def test_unknown_error_normal_copy_hides_raw_exception_but_technical_details_have_request_id() -> None:
    exc = ValueError("private lexical content: the-secret-lyric")
    copy = describe_user_error(exc)
    assert copy.message == "Something unexpected prevented this action."
    assert "the-secret-lyric" not in (copy.title + copy.message + copy.action)

    details = technical_details(exc, request_id="req-123")
    assert "req-123" in details
    assert "ValueError" in details
    assert "the-secret-lyric" not in details


def test_logging_context_keeps_operational_metadata_and_drops_research_payloads(tmp_path: Path) -> None:
    context = sanitize_log_context(
        {
            "event_type": "workbook_read_failed",
            "request_id": "req-1",
            "source_filename": "ratings.xlsx",
            "sheet": "Planilha1",
            "cell": "L28",
            "project_id": "project_1",
            "dataset_id": "dataset_1",
            "annotation_matrix": [["secret"]],
            "lyrics": "private lyric text",
            "workbook_bytes": b"private binary",
            "full_path": str(tmp_path / "private" / "ratings.xlsx"),
        }
    )
    assert context == {
        "event_type": "workbook_read_failed",
        "request_id": "req-1",
        "source_filename": "ratings.xlsx",
        "sheet": "Planilha1",
        "cell": "L28",
        "project_id": "project_1",
        "dataset_id": "dataset_1",
    }


def test_ui_pages_do_not_render_raw_exception_messages() -> None:
    root = Path("src/metaphor_agreement_studio/ui/pages")
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert 'type(exc).__name__' not in text
    assert 'f"Could not inspect {upload.original_display_name}: {exc}"' not in text
