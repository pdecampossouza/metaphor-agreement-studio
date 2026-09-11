from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, AnalysisPerspective
from metaphor_agreement_studio.validation.service import ValidationService


WORKBOOK = Path(__file__).resolve().parents[2] / "imports" / "Testes de concordancia - Braulio.xlsx"

pytestmark = pytest.mark.skipif(
    not WORKBOOK.exists(),
    reason="Optional Bráulio acceptance workbook is not distributed in the public repository",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decision(kind: str, target: str, value: str, index: int) -> ValidationDecision:
    return ValidationDecision(
        decision_id=f"braulio-protocol-{index}",
        decision_type=kind,
        target_id=target,
        original_value=None,
        validated_value=value,
        reason="Bráulio multi-sheet protocol acceptance regression",
        decided_at="2026-09-06T20:00:00+01:00",
    )


def _validated_dataset(study_sheet: str, synthetic_sheet: str):
    service = ValidationService()
    inspection = inspect_workbook(WORKBOOK)
    roles = {
        study_sheet: "study_data",
        synthetic_sheet: "synthetic_example",
    }
    draft = service.prepare_for_worksheet_roles(inspection, roles)

    decisions = [
        _decision("worksheet_role", study_sheet, "study_data", 1),
        _decision("worksheet_role", synthetic_sheet, "synthetic_example", 2),
    ]
    index = 3
    for issue in draft.issues:
        if not issue.blocks_validation:
            continue
        if issue.decision_type == "annotation_mapping":
            value = "confirm_green_metaphor_red_non_metaphor"
        elif issue.decision_type == "category_normalization":
            value = "Adjective"
        elif issue.decision_type == "aggregate_role":
            value = "aggregate"
        else:
            raise AssertionError(f"Unhandled blocking issue: {issue.code}")
        decisions.append(
            _decision(issue.decision_type or "", issue.target_id or "", value, index)
        )
        index += 1

    return service.validate(draft, tuple(decisions))


def test_braulio_two_rater_sheet_reproduces_real_study_controls_without_synthetic_data() -> None:
    before = _sha256(WORKBOOK)

    dataset = _validated_dataset("Dois avaliadores", "Mais de dois avaliadores")
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    assert {r.display_name for r in dataset.raters} == {"Eduardo", "Bráulio"}
    assert {ann.original_sheet for ann in dataset.annotations} == {"Dois avaliadores"}
    assert bundle.counts.lexical_units == 97
    assert len(bundle.pairwise) == 1
    assert bundle.pairwise[0].kappa.value == pytest.approx(0.4781829049611476)
    assert bundle.cochran_q is not None
    assert bundle.cochran_q.q == pytest.approx(27.0)
    assert all(group.fleiss_kappa is None for group in bundle.by_category)
    assert all(group.fleiss_kappa is None for group in bundle.by_source)

    assert _sha256(WORKBOOK) == before


def test_braulio_synthetic_multirater_sheet_exercises_fleiss_protocol_without_mixing_real_sheet() -> None:
    dataset = _validated_dataset("Mais de dois avaliadores", "Dois avaliadores")
    braulio_id = next(r.rater_id for r in dataset.raters if r.display_name == "Bráulio")
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            bootstrap_samples=0,
            analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
            reference_rater_id=braulio_id,
        ),
    )

    assert {r.display_name for r in dataset.raters} == {
        "Dulce",
        "Juliana",
        "Carlos",
        "João",
        "Ricardo",
        "Bráulio",
    }
    assert {ann.original_sheet for ann in dataset.annotations} == {"Mais de dois avaliadores"}
    assert bundle.counts.lexical_units == 97
    assert bundle.counts.raters == 6

    fleiss = next(metric for metric in bundle.overall_multirater if metric.metric == "fleiss_kappa")
    assert fleiss.value == pytest.approx(0.6912466843501326)
    assert bundle.cochran_q is not None
    assert bundle.cochran_q.q == pytest.approx(135.0)

    assert bundle.by_category
    assert bundle.by_source
    assert all(group.fleiss_kappa is not None for group in bundle.by_category)
    assert all(group.fleiss_kappa is not None for group in bundle.by_source)

    # In reference-rater mode, the first five pairwise rows are Bráulio versus each other rater.
    assert len(bundle.pairwise) >= 5
    assert all(result.rater_a_id == braulio_id for result in bundle.pairwise[:5])
    compared = {result.rater_b_id for result in bundle.pairwise[:5]}
    assert compared == {r.rater_id for r in dataset.raters if r.rater_id != braulio_id}
