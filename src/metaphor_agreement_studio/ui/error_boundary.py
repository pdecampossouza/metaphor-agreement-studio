from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import html
import traceback
import uuid

from metaphor_agreement_studio.common.errors import (
    AnalysisUnavailable,
    ExportError,
    ProjectOpenError,
    UnsupportedWorkbookError,
    ValidationBlocked,
    WorkbookReadError,
)
from metaphor_agreement_studio.common.logging import log_exception


@dataclass(frozen=True, slots=True)
class UserErrorCopy:
    title: str
    message: str
    action: str


_COPIES = {
    WorkbookReadError: UserErrorCopy(
        "Workbook could not be read",
        "The workbook could not be read safely.",
        "Check that it is a valid Excel workbook, close it if another program is locking it, and try again.",
    ),
    UnsupportedWorkbookError: UserErrorCopy(
        "Workbook format is not supported",
        "This workbook format is not supported for research import.",
        "Choose an .xlsx or .xlsm workbook that is not an Excel temporary file.",
    ),
    ValidationBlocked: UserErrorCopy(
        "Validation still needs your attention",
        "Validation still needs your attention before the dataset can be trusted for analysis.",
        "Review the highlighted mapping, normalization, aggregate, or alignment decisions and confirm them explicitly.",
    ),
    AnalysisUnavailable: UserErrorCopy(
        "Analysis is not available yet",
        "The requested analysis is not available yet for the current dataset state.",
        "Validate the dataset and select enough comparable raters before running the analysis again.",
    ),
    ProjectOpenError: UserErrorCopy(
        "Project could not be opened",
        "The research project could not be opened safely.",
        "Choose a Metaphor Agreement Studio project folder or restore a verified portable backup.",
    ),
    ExportError: UserErrorCopy(
        "Export could not be created",
        "The requested export could not be created.",
        "Check the destination and dataset state, then create the export again.",
    ),
}

_UNKNOWN = UserErrorCopy(
    "Action could not be completed",
    "Something unexpected prevented this action.",
    "No source workbook was modified. Try the action again; if it repeats, open Technical Details and report the request ID.",
)


def describe_user_error(exc: Exception) -> UserErrorCopy:
    for error_type, copy in _COPIES.items():
        if isinstance(exc, error_type):
            return copy
    return _UNKNOWN


def technical_details(exc: Exception, *, request_id: str) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    lines = [f"Request ID: {request_id}", f"Exception type: {type(exc).__name__}"]
    for frame in frames[-8:]:
        lines.append(f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}")
    return "\n".join(lines)


def render_user_error(
    exc: Exception,
    *,
    log_dir: Path | None = None,
    context: dict[str, object] | None = None,
) -> str:
    import streamlit as st

    request_id = f"MAS-{uuid.uuid4().hex[:10].upper()}"
    copy = describe_user_error(exc)
    st.markdown(
        (
            '<section class="mas-error-card" role="alert">'
            f"<strong>{html.escape(copy.title)}</strong>"
            f"<p>{html.escape(copy.message)}</p>"
            f"<p class=\"mas-error-action\">{html.escape(copy.action)}</p>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )
    with st.expander("Technical Details"):
        st.code(technical_details(exc, request_id=request_id))
    if log_dir is not None:
        log_exception(
            exc,
            request_id=request_id,
            log_dir=log_dir,
            context=context,
        )
    return request_id
