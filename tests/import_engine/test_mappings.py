from pathlib import Path

from metaphor_agreement_studio.domain.enums import Classification, IssueSeverity
from metaphor_agreement_studio.import_engine.mappings import infer_annotation_mapping
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from tests.fixtures.workbook_factory import (
    build_conflicting_mapping_workbook,
    build_two_rater_workbook,
)


def test_yes_no_text_confirms_green_red_semantics(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    inspection = inspect_workbook(path)
    cells = inspection.annotation_cells("Planilha1", "L28:M30")

    candidate = infer_annotation_mapping(cells, workbook_theme=inspection.workbook_theme)

    assert candidate.mapping.semantic_positive == Classification.METAPHOR
    assert candidate.mapping.semantic_negative == Classification.NON_METAPHOR
    assert candidate.confidence.value == "high"
    assert "YES" in candidate.evidence.text_labels
    assert "NO" in candidate.evidence.text_labels
    assert set(candidate.mapping.color_family_map) >= {"green", "red"}
    assert candidate.mapping.color_family_map["green"] == Classification.METAPHOR
    assert candidate.mapping.color_family_map["red"] == Classification.NON_METAPHOR


def test_conflicting_label_and_color_semantics_require_action(tmp_path: Path) -> None:
    path = build_conflicting_mapping_workbook(tmp_path / "conflict.xlsx")
    inspection = inspect_workbook(path)
    cells = inspection.annotation_cells("Planilha1", "D5:D6")

    candidate = infer_annotation_mapping(cells, workbook_theme=inspection.workbook_theme)

    assert candidate.confidence.value == "low"
    assert candidate.mapping.semantic_positive == Classification.METAPHOR
    assert any(issue.severity == IssueSeverity.REQUIRES_ACTION for issue in candidate.issues)
    assert any("conflict" in issue.message.casefold() for issue in candidate.issues)
