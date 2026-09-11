from __future__ import annotations

import os
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import (
    AnalysisConfig,
    AnalysisPerspective,
    EstimateStatus,
)
from metaphor_agreement_studio.validation.service import ValidationService


def _researcher_decisions(draft) -> tuple[ValidationDecision, ...]:
    decisions: list[ValidationDecision] = []
    for index, issue in enumerate(draft.issues, start=1):
        if not issue.blocks_validation:
            continue
        if issue.code == "category_normalization_decision":
            decision_type = "category_normalization"
            validated_value = "Adjective"
        elif issue.code in {"confirm_annotation_mapping", "annotation_mapping_conflict"}:
            decision_type = "annotation_mapping"
            validated_value = "confirm_green_metaphor_red_non_metaphor"
        elif issue.code == "aggregate_role_decision":
            decision_type = "aggregate_role"
            validated_value = "aggregate"
        else:
            raise AssertionError(f"Unhandled blocking regression issue: {issue.code}")
        decisions.append(
            ValidationDecision(
                decision_id=f"regression-{index}",
                decision_type=decision_type,
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=validated_value,
                reason="Research workbook regression decision",
                decided_at="2026-09-05T20:30:00+01:00",
            )
        )
    return tuple(decisions)


def test_real_eduardo_workbook_statistics_when_available() -> None:
    raw = os.environ.get("MAS_EDUARDO_WORKBOOK")
    if not raw:
        pytest.skip("Set MAS_EDUARDO_WORKBOOK to run the private research workbook regression.")

    service = ValidationService()
    draft = service.prepare(inspect_workbook(Path(raw)))
    dataset = service.validate(draft, _researcher_decisions(draft))
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    assert bundle.counts.lexical_units == 97
    assert bundle.counts.raters == 2
    assert bundle.counts.total_ratings == 194
    assert bundle.counts.metaphor_ratings == 87
    assert bundle.counts.non_metaphor_ratings == 107
    assert bundle.counts.missing_ratings == 0
    assert dict(bundle.counts.category_counts) == {
        "Adjective": 18,
        "Adverb": 4,
        "Adverb (idiom)": 1,
        "Noun": 44,
        "Phrasal verb": 1,
        "Preposition": 5,
        "Pronoun": 6,
        "Verb": 18,
    }

    pair = bundle.pairwise[0]
    assert pair.raw_agreement.value == pytest.approx(70 / 97)
    assert pair.kappa.value == pytest.approx(0.4781829049611476)
    assert pair.contingency == ((40, 27), (0, 30))

    assert bundle.cochran_q is not None
    assert bundle.cochran_q.q == pytest.approx(27.0)
    assert bundle.cochran_q.degrees_of_freedom == 1
    assert bundle.cochran_q.p_value == pytest.approx(2.0345546145444302e-07)

    expected_sources = {
        "1. Vídeo: Kadouch": (10, 0.5454545454545456, 2.0),
        "2. Vídeo: Batsashvili": (22, 0.35766423357664234, 8.0),
        "3. Vídeo: Mephisto": (37, 0.672566371681416, 6.0),
        "4. Vídeo: Rabinovich": (28, 0.28037383177570085, 11.0),
        "5. Vídeos combinados": (97, 0.4781829049611476, 27.0),
    }
    assert len(bundle.by_source) == 5
    for source in bundle.by_source:
        expected_n, expected_kappa, expected_q = expected_sources[source.display_name]
        assert source.lexical_unit_count == expected_n
        assert source.pairwise[0].kappa.value == pytest.approx(expected_kappa)
        assert source.cochran_q is not None
        assert source.cochran_q.q == pytest.approx(expected_q)

    category_map = {group.display_name: group for group in bundle.by_category}
    assert category_map["Noun"].pairwise[0].kappa.value == pytest.approx(0.7322515212981745)
    assert category_map["Noun"].cochran_q is not None
    assert category_map["Noun"].cochran_q.q == pytest.approx(6.0)
    assert category_map["Adverb"].pairwise[0].kappa.value == pytest.approx(1.0)
    assert category_map["Adverb"].cochran_q is not None
    assert category_map["Adverb"].cochran_q.status == EstimateStatus.NOT_ESTIMABLE_NO_VARIATION
    assert category_map["Phrasal verb"].pairwise[0].kappa.status == EstimateStatus.DESCRIPTIVE_ONLY

    braulio_id = next(rater.rater_id for rater in dataset.raters if rater.display_name == "Bráulio")
    expert_bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.EXPERT_BENCHMARK,
            reference_rater_id=braulio_id,
            bootstrap_samples=0,
        ),
    )
    expert = expert_bundle.expert_benchmark[0]
    assert expert.true_positive == 30
    assert expert.true_negative == 40
    assert expert.false_positive == 0
    assert expert.false_negative == 27
    assert expert.agreement_with_expert.value == pytest.approx(70 / 97)
    assert expert.sensitivity.value == pytest.approx(30 / 57)
    assert expert.specificity.value == pytest.approx(1.0)
    assert expert.precision.value == pytest.approx(1.0)
    assert expert.recall.value == pytest.approx(30 / 57)
