from __future__ import annotations

from pathlib import Path

import pytest

from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.validation.service import ValidationService


BRAULIO_WORKBOOK = (
    Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx"
)

pytestmark = pytest.mark.skipif(
    not BRAULIO_WORKBOOK.exists(),
    reason="Optional Bráulio acceptance workbook is not distributed in the public repository",
)


def _braulio_workbook() -> Path:
    return BRAULIO_WORKBOOK


def test_multisheet_annotation_workbook_requires_role_for_each_worksheet() -> None:
    draft = ValidationService().prepare(inspect_workbook(_braulio_workbook()))

    role_issues = [
        issue for issue in draft.issues if issue.decision_type == "worksheet_role"
    ]

    assert {issue.target_id for issue in role_issues} == {
        "Dois avaliadores",
        "Mais de dois avaliadores",
    }
    assert all(issue.blocks_validation for issue in role_issues)

from metaphor_agreement_studio.domain.imports import ValidationDecision


def _decision(kind: str, target: str, value: str, index: int) -> ValidationDecision:
    return ValidationDecision(
        decision_id=f"worksheet-role-{index}",
        decision_type=kind,
        target_id=target,
        original_value=None,
        validated_value=value,
        reason="Worksheet-role regression",
        decided_at="2026-09-06T19:45:00+01:00",
    )


def _study_sheet_decisions(draft, study_sheet: str, synthetic_sheet: str):
    decisions = [
        _decision("worksheet_role", study_sheet, "study_data", 1),
        _decision("worksheet_role", synthetic_sheet, "synthetic_example", 2),
    ]
    active_rater_names = {
        rater.display_name
        for table in draft.tables
        if table.sheet_name == study_sheet
        for rater in table.rater_columns
    }
    next_index = 3
    for mapping in draft.rater_mappings:
        if mapping.display_name in active_rater_names:
            decisions.append(
                _decision(
                    "annotation_mapping",
                    mapping.rater_id,
                    "confirm_green_metaphor_red_non_metaphor",
                    next_index,
                )
            )
            next_index += 1
    for proposal in draft.normalization_proposals:
        decisions.append(
            _decision(
                "category_normalization",
                proposal.original,
                proposal.proposed,
                next_index,
            )
        )
        next_index += 1
    active_table_ids = {
        table.table_id for table in draft.tables if table.sheet_name == study_sheet
    }
    for candidate in draft.aggregate_candidates:
        if candidate.aggregate_table_id in active_table_ids:
            decisions.append(
                _decision(
                    "aggregate_role",
                    candidate.aggregate_table_id,
                    "aggregate",
                    next_index,
                )
            )
            next_index += 1
    return tuple(decisions)


def test_synthetic_worksheet_is_excluded_without_requiring_its_rater_decisions() -> None:
    service = ValidationService()
    draft = service.prepare(inspect_workbook(_braulio_workbook()))
    decisions = _study_sheet_decisions(
        draft,
        study_sheet="Dois avaliadores",
        synthetic_sheet="Mais de dois avaliadores",
    )

    dataset = service.validate(draft, decisions)

    assert {rater.display_name for rater in dataset.raters} == {"Eduardo", "Bráulio"}
    assert {source.display_name for source in dataset.sources} == {
        "1. Vídeo: Kadouch",
        "2. Vídeo: Batsashvili",
        "3. Vídeo: Mephisto",
        "4. Vídeo: Rabinovich",
        "5. Vídeos combinados",
    }
    assert len(dataset.units) == 194
    assert len(dataset.annotations) == 388
    assert {ann.original_sheet for ann in dataset.annotations} == {"Dois avaliadores"}


def test_multirater_study_sheet_can_be_selected_without_eduardo_mapping_decision() -> None:
    service = ValidationService()
    draft = service.prepare(inspect_workbook(_braulio_workbook()))
    decisions = _study_sheet_decisions(
        draft,
        study_sheet="Mais de dois avaliadores",
        synthetic_sheet="Dois avaliadores",
    )

    dataset = service.validate(draft, decisions)

    assert {rater.display_name for rater in dataset.raters} == {
        "Dulce",
        "Juliana",
        "Carlos",
        "João",
        "Ricardo",
        "Bráulio",
    }
    assert len(dataset.units) == 194
    assert len(dataset.annotations) == 1164
    assert {ann.original_sheet for ann in dataset.annotations} == {"Mais de dois avaliadores"}


def test_single_sheet_workbook_does_not_require_worksheet_role_decision() -> None:
    original = Path(__file__).resolve().parents[2] / "imports" / "Teste de Concordancia - Revisor Eduardo.xlsx"
    draft = ValidationService().prepare(inspect_workbook(original))

    assert not any(issue.decision_type == "worksheet_role" for issue in draft.issues)


def test_synthetic_rater_warnings_do_not_leak_into_validated_quality_notes() -> None:
    service = ValidationService()
    draft = service.prepare(inspect_workbook(_braulio_workbook()))
    decisions = _study_sheet_decisions(
        draft,
        study_sheet="Dois avaliadores",
        synthetic_sheet="Mais de dois avaliadores",
    )

    dataset = service.validate(draft, decisions)
    joined = "\n".join(note.message for note in dataset.quality_notes)

    assert "Dulce" not in joined
    assert "Juliana" not in joined
    assert "Carlos" not in joined
    assert "João" not in joined
    assert "Ricardo" not in joined


def test_prepare_for_worksheet_roles_recomputes_mapping_from_study_data_only() -> None:
    service = ValidationService()
    inspection = inspect_workbook(_braulio_workbook())

    draft = service.prepare_for_worksheet_roles(
        inspection,
        {
            "Dois avaliadores": "study_data",
            "Mais de dois avaliadores": "synthetic_example",
        },
    )

    assert {table.sheet_name for table in draft.tables} == {"Dois avaliadores"}
    assert {mapping.display_name for mapping in draft.rater_mappings} == {"Eduardo", "Bráulio"}
    braulio = next(mapping for mapping in draft.rater_mappings if mapping.display_name == "Bráulio")
    assert braulio.cell_count == 194
    assert not any(issue.decision_type == "worksheet_role" for issue in draft.issues)
