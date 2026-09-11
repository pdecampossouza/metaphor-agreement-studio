from __future__ import annotations

import numpy as np
from statsmodels.stats.inter_rater import fleiss_kappa as sm_fleiss_kappa

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.matrices import complete_binary_matrix
from metaphor_agreement_studio.statistics.types import EstimateStatus, MetricResult


def _no_variation(values: np.ndarray) -> bool:
    observed = values[~np.isnan(values)]
    return len(observed) > 0 and len(np.unique(observed)) == 1


def fleiss_kappa(
    dataset: ValidatedDataset,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...] | None = None,
) -> MetricResult:
    matrix = complete_binary_matrix(dataset, rater_ids, unit_ids)
    complete = matrix.values[matrix.complete_row_mask]
    n = len(complete)
    had_incomplete = n < len(matrix.unit_ids)
    explanation = ("fleiss_complete_cases_only",) if had_incomplete else ()

    if n == 0:
        return MetricResult(
            metric="fleiss_kappa",
            value=None,
            status=EstimateStatus.INCOMPLETE_FOR_METRIC,
            effective_n=0,
            explanation_keys=explanation + ("no_complete_multirater_observations",),
        )
    if n == 1:
        return MetricResult(
            metric="fleiss_kappa",
            value=None,
            status=EstimateStatus.DESCRIPTIVE_ONLY,
            effective_n=1,
            explanation_keys=explanation + ("one_item_descriptive_only",),
        )
    if _no_variation(complete):
        return MetricResult(
            metric="fleiss_kappa",
            value=None,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            effective_n=n,
            explanation_keys=explanation + ("perfect_agreement_no_variation",),
        )

    category_counts = np.column_stack(
        ((complete == 0).sum(axis=1), (complete == 1).sum(axis=1))
    ).astype(float)
    value = float(sm_fleiss_kappa(category_counts))
    if not np.isfinite(value):
        return MetricResult(
            metric="fleiss_kappa",
            value=None,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            effective_n=n,
            explanation_keys=explanation + ("kappa_no_chance_variation",),
        )
    return MetricResult(
        metric="fleiss_kappa",
        value=value,
        status=EstimateStatus.OK,
        effective_n=n,
        explanation_keys=explanation,
    )


def _nominal_alpha_fallback(values: np.ndarray) -> float | None:
    # Coincidence-matrix implementation of Krippendorff's nominal alpha.
    categories = (0, 1)
    coincidence = np.zeros((2, 2), dtype=float)
    usable_units = 0
    for row in values:
        observed = row[~np.isnan(row)].astype(int)
        m = len(observed)
        if m < 2:
            continue
        usable_units += 1
        counts = np.array([np.sum(observed == category) for category in categories], dtype=float)
        for left in range(2):
            for right in range(2):
                if left == right:
                    coincidence[left, right] += (
                        counts[left] * (counts[left] - 1) / (m - 1)
                    )
                else:
                    coincidence[left, right] += counts[left] * counts[right] / (m - 1)
    if usable_units == 0:
        return None
    total = float(coincidence.sum())
    if total <= 1:
        return None
    marginals = coincidence.sum(axis=0)
    expected = np.zeros((2, 2), dtype=float)
    for left in range(2):
        for right in range(2):
            if left == right:
                expected[left, right] = marginals[left] * (marginals[left] - 1) / (total - 1)
            else:
                expected[left, right] = marginals[left] * marginals[right] / (total - 1)

    observed_disagreement = float((coincidence.sum() - np.trace(coincidence)) / total)
    expected_disagreement = float((expected.sum() - np.trace(expected)) / total)
    if np.isclose(expected_disagreement, 0.0):
        return None
    value = 1.0 - observed_disagreement / expected_disagreement
    return float(value) if np.isfinite(value) else None


def krippendorff_alpha(
    dataset: ValidatedDataset,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...] | None = None,
) -> MetricResult:
    matrix = complete_binary_matrix(dataset, rater_ids, unit_ids)
    observed_per_unit = (~np.isnan(matrix.values)).sum(axis=1)
    usable_mask = observed_per_unit >= 2
    usable = matrix.values[usable_mask]
    n = len(usable)
    if n == 0:
        return MetricResult(
            metric="krippendorff_alpha",
            value=None,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            effective_n=0,
            explanation_keys=("krippendorff_requires_two_ratings_per_unit",),
        )
    if n == 1:
        return MetricResult(
            metric="krippendorff_alpha",
            value=None,
            status=EstimateStatus.DESCRIPTIVE_ONLY,
            effective_n=1,
            explanation_keys=("one_item_descriptive_only",),
        )
    if _no_variation(usable):
        return MetricResult(
            metric="krippendorff_alpha",
            value=None,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            effective_n=n,
            explanation_keys=("perfect_agreement_no_variation",),
        )

    value = _nominal_alpha_fallback(usable)

    if value is None or not np.isfinite(value):
        return MetricResult(
            metric="krippendorff_alpha",
            value=None,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            effective_n=n,
            explanation_keys=("alpha_no_expected_disagreement",),
        )

    explanation: list[str] = []
    if np.isnan(usable).any():
        explanation.append("krippendorff_missing_tolerant")
    explanation.append("krippendorff_internal_nominal_fallback")
    return MetricResult(
        metric="krippendorff_alpha",
        value=float(value),
        status=EstimateStatus.OK,
        effective_n=n,
        explanation_keys=tuple(explanation),
    )
