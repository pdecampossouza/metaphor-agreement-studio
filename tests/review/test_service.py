from __future__ import annotations

from dataclasses import dataclass

import pytest

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.review.service import build_rater_profile, build_review_cases
from metaphor_agreement_studio.review.types import ReviewStatus
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def _annotation(unit: str, rater: str, value: Classification, index: int) -> Annotation:
    return Annotation(
        annotation_id=f"a{index}",
        unit_id=unit,
        rater_id=rater,
        classification=value,
        import_id="fixture",
        original_sheet="Sheet1",
        original_cell=f"A{index}",
        original_raw_value=value.value,
        original_style={},
        detection_method="fixture",
        validation_status=ValidationStatus.VALIDATED,
    )


@pytest.fixture
def review_dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("all_m", "fire", "Noun", "s1", 1),
        LexicalUnit("all_nm", "hand", "Noun", "s1", 1),
        LexicalUnit("two_vs_one", "fall", "Verb", "s1", 1),
        LexicalUnit("missing", "echo", "Noun", "s1", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    values = {
        "all_m": (Classification.METAPHOR, Classification.METAPHOR, Classification.METAPHOR),
        "all_nm": (
            Classification.NON_METAPHOR,
            Classification.NON_METAPHOR,
            Classification.NON_METAPHOR,
        ),
        "two_vs_one": (
            Classification.METAPHOR,
            Classification.METAPHOR,
            Classification.NON_METAPHOR,
        ),
        "missing": (
            Classification.NON_METAPHOR,
            Classification.MISSING,
            Classification.NON_METAPHOR,
        ),
    }
    annotations: list[Annotation] = []
    i = 0
    for unit in units:
        for rater, value in zip(raters, values[unit.unit_id], strict=True):
            i += 1
            annotations.append(_annotation(unit.unit_id, rater.rater_id, value, i))
    return ValidatedDataset(
        dataset_id="review",
        sources=(Source("s1", "Example"),),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_review_cases_distinguish_unanimity_from_disagreement(review_dataset) -> None:
    cases = {case.unit_id: case for case in build_review_cases(review_dataset)}

    assert cases["all_m"].status is ReviewStatus.UNANIMOUS_METAPHOR
    assert cases["all_nm"].status is ReviewStatus.UNANIMOUS_NON_METAPHOR
    assert cases["two_vs_one"].status is ReviewStatus.DISAGREEMENT
    assert cases["missing"].has_missing is True
    assert cases["missing"].status is ReviewStatus.UNANIMOUS_NON_METAPHOR


def test_majority_is_descriptive_and_never_ground_truth(review_dataset) -> None:
    case = next(case for case in build_review_cases(review_dataset) if case.unit_id == "two_vs_one")

    assert case.majority_classification is Classification.METAPHOR
    assert case.adjudicated_classification is None
    assert case.divergent_rater_ids == ("r3",)
    assert not hasattr(case, "correct_rater")
    assert not hasattr(case, "ground_truth")


def test_review_cases_prioritize_disagreement_then_missing(review_dataset) -> None:
    cases = build_review_cases(review_dataset)

    assert cases[0].unit_id == "two_vs_one"
    assert cases[1].unit_id == "missing"


def test_selected_raters_change_review_case_without_mutating_dataset(review_dataset) -> None:
    cases = build_review_cases(review_dataset, selected_raters=("r1", "r2"))
    split = next(case for case in cases if case.unit_id == "two_vs_one")

    assert split.status is ReviewStatus.UNANIMOUS_METAPHOR
    assert len(review_dataset.raters) == 3


def test_rater_profile_reports_divergence_descriptors_not_quality_scores(review_dataset) -> None:
    bundle = analyze_dataset(review_dataset, AnalysisConfig(bootstrap_samples=0))

    profile = build_rater_profile(review_dataset, "r3", bundle)

    assert profile.focus_rater_id == "r3"
    assert profile.metaphor_rate == pytest.approx(0.25)
    assert profile.non_metaphor_rate == pytest.approx(0.75)
    assert profile.missing_rate == pytest.approx(0.0)
    assert profile.differs_from_all_count == 1
    assert profile.agrees_with_majority_count == 3
    assert profile.mean_pairwise_kappa is not None
    assert not hasattr(profile, "quality_score")


def test_rater_profile_uses_analysis_scope_and_does_not_double_count_aggregate(review_dataset) -> None:
    from dataclasses import replace

    aggregate_unit = LexicalUnit("agg_u1", "fire", "Noun", "agg", 1)
    aggregate_annotations = tuple(
        _annotation("agg_u1", rater.rater_id, Classification.METAPHOR, 100 + index)
        for index, rater in enumerate(review_dataset.raters, 1)
    )
    dataset = replace(
        review_dataset,
        dataset_id="review-with-aggregate",
        sources=review_dataset.sources + (Source("agg", "Combined", is_aggregate=True),),
        units=review_dataset.units + (aggregate_unit,),
        annotations=review_dataset.annotations + aggregate_annotations,
    )
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    profile = build_rater_profile(dataset, "r3", bundle)

    assert profile.total_units == 4
    assert profile.metaphor_rate == pytest.approx(0.25)
