from __future__ import annotations

import pytest

from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import (
    AnalysisConfig,
    AnalysisPerspective,
    EstimateStatus,
)


def test_reference_rater_mode_orders_reference_comparisons_first(binary_dataset) -> None:
    config = AnalysisConfig(
        analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
        reference_rater_id="r2",
        bootstrap_samples=0,
    )

    bundle = analyze_dataset(binary_dataset, config)

    assert [(pair.rater_a_id, pair.rater_b_id) for pair in bundle.pairwise] == [
        ("r2", "r1"),
        ("r2", "r3"),
        ("r1", "r3"),
    ]
    assert bundle.expert_benchmark == ()


def test_no_reference_mode_keeps_symmetric_pairwise_analysis(binary_dataset) -> None:
    bundle = analyze_dataset(
        binary_dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.NO_REFERENCE,
            bootstrap_samples=0,
        ),
    )

    assert [(pair.rater_a_id, pair.rater_b_id) for pair in bundle.pairwise] == [
        ("r1", "r2"),
        ("r1", "r3"),
        ("r2", "r3"),
    ]
    assert bundle.expert_benchmark == ()


def test_expert_benchmark_reports_confusion_and_classification_metrics(binary_dataset) -> None:
    config = AnalysisConfig(
        analysis_perspective=AnalysisPerspective.EXPERT_BENCHMARK,
        reference_rater_id="r2",
        bootstrap_samples=0,
    )

    bundle = analyze_dataset(binary_dataset, config)

    assert len(bundle.expert_benchmark) == 2
    comparison = next(result for result in bundle.expert_benchmark if result.rater_id == "r1")
    assert comparison.benchmark_rater_id == "r2"
    assert comparison.effective_n == 4
    assert comparison.true_positive == 1
    assert comparison.true_negative == 2
    assert comparison.false_positive == 1
    assert comparison.false_negative == 0
    assert comparison.agreement_with_expert.value == pytest.approx(0.75)
    assert comparison.sensitivity.value == pytest.approx(1.0)
    assert comparison.specificity.value == pytest.approx(2 / 3)
    assert comparison.precision.value == pytest.approx(0.5)
    assert comparison.recall.value == pytest.approx(1.0)


def test_expert_metric_is_explained_when_denominator_is_absent(binary_dataset) -> None:
    from dataclasses import replace

    from metaphor_agreement_studio.domain.enums import Classification

    annotations = tuple(
        replace(annotation, classification=Classification.NON_METAPHOR)
        if annotation.rater_id == "r2"
        else annotation
        for annotation in binary_dataset.annotations
    )
    dataset = replace(binary_dataset, dataset_id="no-positive-expert", annotations=annotations)
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.EXPERT_BENCHMARK,
            reference_rater_id="r2",
            bootstrap_samples=0,
        ),
    )

    comparison = next(result for result in bundle.expert_benchmark if result.rater_id == "r1")
    assert comparison.sensitivity.value is None
    assert comparison.sensitivity.status == EstimateStatus.DESCRIPTIVE_ONLY
    assert "benchmark_no_positive_cases" in comparison.sensitivity.explanation_keys


def test_reference_modes_require_a_valid_selected_rater(binary_dataset) -> None:
    with pytest.raises(ValueError, match="reference rater"):
        analyze_dataset(
            binary_dataset,
            AnalysisConfig(
                analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
                bootstrap_samples=0,
            ),
        )

    with pytest.raises(ValueError, match="Unknown reference rater"):
        analyze_dataset(
            binary_dataset,
            AnalysisConfig(
                analysis_perspective=AnalysisPerspective.EXPERT_BENCHMARK,
                reference_rater_id="missing",
                bootstrap_samples=0,
            ),
        )
