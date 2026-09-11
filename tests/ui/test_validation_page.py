from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.ui.pages.annotations import annotation_records
from metaphor_agreement_studio.ui.pages.validation import validation_summary
from metaphor_agreement_studio.validation.service import ValidationService
from tests.fixtures.workbook_factory import build_two_rater_workbook


def _decisions(draft):
    output = []
    for index, issue in enumerate(draft.issues, start=1):
        if not issue.blocks_validation:
            continue
        if issue.code == "confirm_annotation_mapping":
            decision_type = "annotation_mapping"
            value = "confirm_green_metaphor_red_non_metaphor"
        elif issue.code == "category_normalization_decision":
            decision_type = "category_normalization"
            value = "Adjective"
        elif issue.code == "aggregate_role_decision":
            decision_type = "aggregate_role"
            value = "aggregate"
        else:
            raise AssertionError(issue.code)
        output.append(
            ValidationDecision(
                decision_id=f"d{index}",
                decision_type=decision_type,
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=value,
                reason="UI test",
                decided_at="2026-09-05T20:30:00+01:00",
            )
        )
    return tuple(output)


def test_validation_summary_explains_detected_research_structure(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    draft = ValidationService().prepare(inspect_workbook(path))

    summary = validation_summary(draft)

    assert summary["workbook"] == "ratings.xlsx"
    assert summary["worksheets"] == 1
    assert summary["tables"] == 1
    assert summary["raters"] == ("Eduardo", "Braulio")
    assert summary["normalization_count"] == 1
    assert summary["blocking_issues"] == 2
    assert summary["style_groups"] >= 2


def test_annotation_records_present_validated_raters_side_by_side(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    service = ValidationService()
    draft = service.prepare(inspect_workbook(path))
    dataset = service.validate(draft, _decisions(draft))

    rows = annotation_records(dataset)

    assert len(rows) == 3
    top = next(row for row in rows if row["Lexical unit"] == "top")
    assert top["Grammatical category"] == "Adjective"
    assert top["Eduardo"] == "Non-metaphor"
    assert top["Braulio"] == "Metaphor"
    assert top["Agreement state"] == "Disagreement"


def test_streamlit_validation_workspace_shows_required_research_copy_when_available(
    tmp_path: Path, monkeypatch
) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    build_two_rater_workbook(tmp_path / "ratings.xlsx")
    monkeypatch.setenv("MAS_WORKSPACE", str(tmp_path))
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()
    inspect_button = next(button for button in app.button if button.label == "Inspect & Validate")
    app = inspect_button.click().run()
    rendered = "\n".join(
        str(element.value)
        for collection in (app.markdown, app.info, app.caption)
        for element in collection
    )
    assert "Please verify the extracted data before running the analysis." in rendered
    assert "ratings.xlsx" in rendered


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx").exists(),
    reason="Optional Bráulio acceptance workbook is not distributed in the public repository",
)
def test_multisheet_validation_scope_hides_synthetic_raters_and_tables() -> None:
    from metaphor_agreement_studio.ui.pages.validation import (
        validation_scope_for_worksheet_roles,
        worksheet_role_sheet_names,
    )

    path = Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx"
    draft = ValidationService().prepare(inspect_workbook(path))

    assert worksheet_role_sheet_names(draft) == (
        "Dois avaliadores",
        "Mais de dois avaliadores",
    )
    scope = validation_scope_for_worksheet_roles(
        draft,
        {
            "Dois avaliadores": "study_data",
            "Mais de dois avaliadores": "synthetic_example",
        },
    )

    assert scope["study_sheets"] == ("Dois avaliadores",)
    assert scope["rater_names"] == ("Eduardo", "Bráulio")
    assert len(scope["table_ids"]) == 5
    assert len(scope["aggregate_ids"]) == 1


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx").exists(),
    reason="Optional Bráulio acceptance workbook is not distributed in the public repository",
)
def test_source_summary_marks_synthetic_worksheet_as_excluded() -> None:
    from metaphor_agreement_studio.ui.pages.validation import source_summary_records

    path = Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx"
    draft = ValidationService().prepare(inspect_workbook(path))
    rows = source_summary_records(
        draft,
        {
            "Dois avaliadores": "study_data",
            "Mais de dois avaliadores": "synthetic_example",
        },
    )

    synthetic = [row for row in rows if row["Worksheet"] == "Mais de dois avaliadores"]
    study = [row for row in rows if row["Worksheet"] == "Dois avaliadores"]
    assert synthetic and all(row["Worksheet role"] == "Synthetic / example — excluded" for row in synthetic)
    assert study and all(row["Worksheet role"] == "Study data" for row in study)
