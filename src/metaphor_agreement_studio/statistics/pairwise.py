from __future__ import annotations

import numpy as np

from metaphor_agreement_studio.statistics.descriptive import raw_pairwise_agreement
from metaphor_agreement_studio.statistics.types import EstimateStatus, MetricResult, PairwiseResult


def _paired_complete(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Pairwise vectors must have the same shape")
    mask = ~np.isnan(a) & ~np.isnan(b)
    return a[mask], b[mask]


def _kappa_value(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) == 0:
        return None
    observed = float(np.mean(a == b))
    p_a_positive = float(np.mean(a == 1))
    p_b_positive = float(np.mean(b == 1))
    expected = p_a_positive * p_b_positive + (1 - p_a_positive) * (1 - p_b_positive)
    denominator = 1.0 - expected
    if np.isclose(denominator, 0.0):
        return None
    value = (observed - expected) / denominator
    if not np.isfinite(value):
        return None
    return float(value)


def _contingency(a: np.ndarray, b: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]]:
    # Rows are rater A (0, 1); columns are rater B (0, 1).
    n00 = int(np.sum((a == 0) & (b == 0)))
    n01 = int(np.sum((a == 0) & (b == 1)))
    n10 = int(np.sum((a == 1) & (b == 0)))
    n11 = int(np.sum((a == 1) & (b == 1)))
    return ((n00, n01), (n10, n11))


def _bootstrap_interval(
    a: np.ndarray,
    b: np.ndarray,
    *,
    confidence: float,
    bootstrap_samples: int,
    seed: int,
) -> tuple[float | None, float | None]:
    if bootstrap_samples <= 0 or len(a) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(bootstrap_samples):
        indices = rng.integers(0, len(a), size=len(a))
        estimate = _kappa_value(a[indices], b[indices])
        if estimate is not None:
            values.append(estimate)
    required = max(100, bootstrap_samples // 4)
    if len(values) < required:
        return None, None
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(np.asarray(values), [alpha, 1.0 - alpha])
    return float(low), float(high)


def cohen_kappa(
    a: np.ndarray,
    b: np.ndarray,
    *,
    confidence: float = 0.95,
    bootstrap_samples: int = 2000,
    seed: int = 20260905,
    rater_a_id: str = "",
    rater_b_id: str = "",
) -> PairwiseResult:
    complete_a, complete_b = _paired_complete(a, b)
    raw = raw_pairwise_agreement(complete_a, complete_b)
    n = len(complete_a)
    contingency = _contingency(complete_a, complete_b)

    if n == 0:
        kappa = MetricResult(
            metric="cohen_kappa",
            value=None,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            effective_n=0,
            explanation_keys=("no_complete_pairwise_observations",),
        )
    elif n == 1:
        kappa = MetricResult(
            metric="cohen_kappa",
            value=None,
            status=EstimateStatus.DESCRIPTIVE_ONLY,
            effective_n=1,
            explanation_keys=("one_item_descriptive_only",),
        )
    else:
        estimate = _kappa_value(complete_a, complete_b)
        if estimate is None:
            explanation = (
                "perfect_agreement_no_variation"
                if raw.value == 1.0
                else "kappa_no_chance_variation"
            )
            kappa = MetricResult(
                metric="cohen_kappa",
                value=None,
                status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
                effective_n=n,
                explanation_keys=(explanation,),
            )
        else:
            ci_low, ci_high = _bootstrap_interval(
                complete_a,
                complete_b,
                confidence=confidence,
                bootstrap_samples=bootstrap_samples,
                seed=seed,
            )
            kappa = MetricResult(
                metric="cohen_kappa",
                value=estimate,
                status=EstimateStatus.OK,
                effective_n=n,
                ci_low=ci_low,
                ci_high=ci_high,
            )

    return PairwiseResult(
        rater_a_id=rater_a_id,
        rater_b_id=rater_b_id,
        raw_agreement=raw,
        kappa=kappa,
        contingency=contingency,
    )
