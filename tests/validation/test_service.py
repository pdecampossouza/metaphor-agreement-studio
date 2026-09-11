from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.validation.service import ValidationBlocked, ValidationService
from tests.fixtures.workbook_factory import (
    build_conflicting_mapping_workbook,
    build_two_rater_workbook,
)


def decisions_for_all_blocking_issues(draft):
    decisions = []
    for index, issue in enumerate(draft.issues, start=1):
        if not issue.blocks_validation:
            continue
        if issue.code == "category_normalization_decision":
            validated_value = "Adjective"
            decision_type = "category_normalization"
        elif issue.code in {"confirm_annotation_mapping", "annotation_mapping_conflict"}:
            validated_value = "confirm_green_metaphor_red_non_metaphor"
            decision_type = "annotation_mapping"
        elif issue.code == "aggregate_role_decision":
            validated_value = "aggregate"
            decision_type = "aggregate_role"
        else:
            raise AssertionError(f"Unhandled blocking test issue: {issue.code}")
        decisions.append(
            ValidationDecision(
                decision_id=f"decision-{index}",
                decision_type=decision_type,
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=validated_value,
                reason="Test researcher decision",
                decided_at="2026-09-05T20:30:00+01:00",
            )
        )
    return tuple(decisions)


def test_requires_action_issue_blocks_dataset_validation(tmp_path: Path) -> None:
    path = build_conflicting_mapping_workbook(tmp_path / "conflict.xlsx")
    draft = ValidationService().prepare(inspect_workbook(path))

    assert any(issue.code == "annotation_mapping_conflict" for issue in draft.issues)
    with pytest.raises(ValidationBlocked) as exc:
        ValidationService().validate(draft, decisions=())

    assert "annotation mapping" in str(exc.value).lower()


def test_validated_dataset_preserves_raw_typo_but_applies_accepted_normalization(
    tmp_path: Path,
) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    inspection = inspect_workbook(path)
    service = ValidationService()
    draft = service.prepare(inspection)

    dataset = service.validate(draft, decisions_for_all_blocking_issues(draft))

    top = next(unit for unit in dataset.units if unit.lexical_unit == "top")
    assert top.grammatical_category == "Adjective"
    assert inspection.sheet("Planilha1").cell("K28").raw_value == "Adjetive"
    assert len(dataset.raters) == 2
    assert len(dataset.annotations) == 6
    assert all(annotation.original_cell for annotation in dataset.annotations)
    assert all(annotation.original_style for annotation in dataset.annotations)


def test_researcher_can_explicitly_reverse_style_only_mapping(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    service = ValidationService()
    draft = service.prepare(inspect_workbook(path))
    decisions = list(decisions_for_all_blocking_issues(draft))
    decisions = [
        ValidationDecision(
            decision_id=item.decision_id,
            decision_type=item.decision_type,
            target_id=item.target_id,
            original_value=item.original_value,
            validated_value=(
                "green_non_metaphor_red_metaphor"
                if item.decision_type == "annotation_mapping"
                else item.validated_value
            ),
            reason=item.reason,
            decided_at=item.decided_at,
            actor=item.actor,
        )
        for item in decisions
    ]

    dataset = service.validate(draft, tuple(decisions))
    unit_by_id = {unit.unit_id: unit for unit in dataset.units}
    rater_by_id = {rater.rater_id: rater.display_name for rater in dataset.raters}
    top_braulio = next(
        annotation
        for annotation in dataset.annotations
        if unit_by_id[annotation.unit_id].lexical_unit == "top"
        and rater_by_id[annotation.rater_id] == "Braulio"
    )

    assert top_braulio.classification.value == "NON_METAPHOR"
