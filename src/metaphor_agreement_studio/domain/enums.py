from enum import StrEnum


class Classification(StrEnum):
    METAPHOR = "METAPHOR"
    NON_METAPHOR = "NON_METAPHOR"
    MISSING = "MISSING"


class ValidationStatus(StrEnum):
    DETECTED = "detected"
    NEEDS_REVIEW = "needs_review"
    VALIDATED = "validated"


class IssueSeverity(StrEnum):
    INFORMATION = "information"
    WARNING = "warning"
    REQUIRES_ACTION = "requires_action"


class SourceType(StrEnum):
    TABLE = "table"
    AGGREGATE = "aggregate"
