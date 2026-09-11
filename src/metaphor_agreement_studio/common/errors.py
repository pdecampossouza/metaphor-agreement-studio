from __future__ import annotations


class UserFacingError(RuntimeError):
    """Base application error whose raw message is for diagnostics, not normal UI copy."""


class WorkbookReadError(UserFacingError):
    """The selected workbook could not be inspected safely."""


class UnsupportedWorkbookError(UserFacingError):
    """The selected file is not a supported workbook input."""


class ValidationBlocked(UserFacingError):
    """Required researcher validation decisions are still unresolved."""


class AnalysisUnavailable(UserFacingError):
    """Analysis cannot run for the current validated state."""


class ProjectOpenError(UserFacingError):
    """A persistent project could not be opened safely."""


class ExportError(UserFacingError):
    """A requested research export could not be generated."""
