from __future__ import annotations

import numpy as np

from metaphor_agreement_studio.statistics.matrices import (
    complete_binary_matrix,
    pairwise_vectors,
)
from metaphor_agreement_studio.statistics.types import AnalysisConfig, EstimateStatus, MetricResult


def test_pairwise_vectors_drop_only_missing_overlap(dataset_with_missing) -> None:
    vectors = pairwise_vectors(dataset_with_missing, "r1", "r2")

    assert vectors.effective_n == 3
    assert vectors.unit_ids == ("u1", "u2", "u4")
    assert vectors.a.tolist() == [1.0, 0.0, 0.0]
    assert vectors.b.tolist() == [1.0, 0.0, 0.0]
    assert not np.isnan(vectors.a).any()
    assert not np.isnan(vectors.b).any()


def test_complete_binary_matrix_preserves_missing_for_missing_aware_metrics(
    dataset_with_missing,
) -> None:
    matrix = complete_binary_matrix(dataset_with_missing, ("r1", "r2", "r3"))

    assert matrix.values.shape == (4, 3)
    assert matrix.unit_ids == ("u1", "u2", "u3", "u4")
    assert matrix.rater_ids == ("r1", "r2", "r3")
    assert np.isnan(matrix.values[2, 1])
    assert np.isnan(matrix.values[3, 2])
    assert matrix.complete_row_mask.tolist() == [True, True, False, False]


def test_result_contract_uses_none_for_non_estimable_values() -> None:
    result = MetricResult(
        metric="cohen_kappa",
        value=None,
        status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
        effective_n=3,
    )

    assert result.value is None
    assert result.status.value == "not_estimable_no_variation"


def test_analysis_config_has_reproducible_defaults() -> None:
    config = AnalysisConfig()

    assert config.confidence_level == 0.95
    assert config.multiple_testing_correction == "holm"
    assert config.bootstrap_samples == 2000
    assert config.random_seed == 20260905


def test_analyze_dataset_rejects_non_validated_input() -> None:
    from metaphor_agreement_studio.statistics.engine import analyze_dataset

    try:
        analyze_dataset(object(), AnalysisConfig())  # type: ignore[arg-type]
    except TypeError as exc:
        assert "ValidatedDataset" in str(exc)
    else:
        raise AssertionError("Raw/unvalidated objects must be rejected")


def test_analysis_bundle_includes_posthoc_tendency_with_requested_correction(binary_dataset) -> None:
    from metaphor_agreement_studio.statistics.engine import analyze_dataset

    bundle = analyze_dataset(
        binary_dataset,
        AnalysisConfig(
            bootstrap_samples=0,
            multiple_testing_correction="holm",
        ),
    )

    assert len(bundle.posthoc_tendency) == 3
    assert all(item.adjusted_p_value is not None for item in bundle.posthoc_tendency)
    assert bundle.config.multiple_testing_correction == "holm"
