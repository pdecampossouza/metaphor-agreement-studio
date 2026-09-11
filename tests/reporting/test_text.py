from __future__ import annotations

from metaphor_agreement_studio.reporting.text import (
    REPORTING_WARNING,
    generate_method_summary,
    suggest_statistical_reporting,
)
from metaphor_agreement_studio.statistics.types import AnalysisConfig, EstimateStatus, MetricResult, PairwiseResult


def test_non_estimable_reporting_explains_complete_agreement_without_nan() -> None:
    result = PairwiseResult(
        "r1",
        "r2",
        MetricResult("raw_agreement", 1.0, EstimateStatus.OK, 7),
        MetricResult("cohen_kappa", None, EstimateStatus.NOT_ESTIMABLE_NO_VARIATION, 7),
        ((0, 0), (0, 7)),
    )
    text = suggest_statistical_reporting(result)
    assert "observed agreement was complete" in text.lower()
    assert "not estimable" in text.lower()
    assert "absence of variation" in text.lower()
    assert "nan" not in text.lower()
    assert REPORTING_WARNING in text


def test_method_summary_reflects_actual_analysis_configuration() -> None:
    config = AnalysisConfig(multiple_testing_correction="holm", selected_categories=("Noun", "Verb"))
    text = generate_method_summary(config, rater_count=3)
    assert "three raters" in text.lower()
    assert "fleiss" in text.lower()
    assert "cochran" in text.lower()
    assert "holm" in text.lower()
    assert "pairwise" in text.lower()
