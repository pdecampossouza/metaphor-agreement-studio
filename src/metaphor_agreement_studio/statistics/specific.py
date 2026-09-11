from __future__ import annotations

import numpy as np

from metaphor_agreement_studio.statistics.types import (
    EstimateStatus,
    MetricResult,
    SpecificAgreementResult,
)


def _specific_metric(metric: str, numerator: int, denominator: int, n: int) -> MetricResult:
    if n == 0:
        return MetricResult(
            metric=metric,
            value=None,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            effective_n=0,
            explanation_keys=("no_complete_pairwise_observations",),
        )
    if denominator == 0:
        return MetricResult(
            metric=metric,
            value=None,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            effective_n=n,
            explanation_keys=("class_absent_specific_agreement",),
        )
    return MetricResult(
        metric=metric,
        value=float(numerator / denominator),
        status=EstimateStatus.OK,
        effective_n=n,
    )


def specific_agreement(
    a: np.ndarray,
    b: np.ndarray,
    positive_value: int = 1,
    *,
    rater_a_id: str = "",
    rater_b_id: str = "",
) -> SpecificAgreementResult:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Pairwise vectors must have the same shape")
    mask = ~np.isnan(a) & ~np.isnan(b)
    a = a[mask]
    b = b[mask]
    n = len(a)

    positive = float(positive_value)
    negative = 0.0 if positive == 1.0 else 1.0
    both_positive = int(np.sum((a == positive) & (b == positive)))
    a_only = int(np.sum((a == positive) & (b == negative)))
    b_only = int(np.sum((a == negative) & (b == positive)))
    both_negative = int(np.sum((a == negative) & (b == negative)))

    positive_denominator = 2 * both_positive + a_only + b_only
    negative_denominator = 2 * both_negative + a_only + b_only

    return SpecificAgreementResult(
        rater_a_id=rater_a_id,
        rater_b_id=rater_b_id,
        metaphor_agreement=_specific_metric(
            "specific_metaphor_agreement",
            2 * both_positive,
            positive_denominator,
            n,
        ),
        non_metaphor_agreement=_specific_metric(
            "specific_non_metaphor_agreement",
            2 * both_negative,
            negative_denominator,
            n,
        ),
    )
