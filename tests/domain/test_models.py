import dataclasses
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.enums import Classification, IssueSeverity
from metaphor_agreement_studio.domain.models import LexicalUnit, WorkbookCandidate


def test_classification_has_only_current_analytical_states() -> None:
    assert [x.value for x in Classification] == ["METAPHOR", "NON_METAPHOR", "MISSING"]


def test_lexical_unit_is_immutable_and_occurrence_aware() -> None:
    unit = LexicalUnit(
        unit_id="kadouch:hand:1",
        lexical_unit="hand",
        grammatical_category="Noun",
        source_id="kadouch",
        occurrence_index=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        unit.lexical_unit = "hands"  # type: ignore[misc]


def test_workbook_candidate_preserves_absolute_source_path(tmp_path: Path) -> None:
    path = (tmp_path / "study.xlsx").resolve()
    candidate = WorkbookCandidate(
        path=path,
        display_name="study.xlsx",
        discovery_root=tmp_path.resolve(),
    )
    assert candidate.path == path
    assert IssueSeverity.REQUIRES_ACTION.value == "requires_action"
