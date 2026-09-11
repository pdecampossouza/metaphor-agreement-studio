from __future__ import annotations

from dataclasses import dataclass

from metaphor_agreement_studio.domain.enums import IssueSeverity


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    issue_id: str
    code: str
    severity: IssueSeverity
    message: str
    target_id: str | None = None
    decision_type: str | None = None

    @property
    def blocks_validation(self) -> bool:
        return self.severity == IssueSeverity.REQUIRES_ACTION
