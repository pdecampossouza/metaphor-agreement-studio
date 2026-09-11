from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy.stats import chi2
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests

from metaphor_agreement_studio.statistics.types import (
    CochranQResult,
    EstimateStatus,
    PairwiseTestResult,
)


def _complete_rows(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2:
        raise ValueError("Cochran Q requires a two-dimensional unit-by-rater matrix")
    return values[~np.isnan(values).any(axis=1)]


def cochran_q(matrix: np.ndarray) -> CochranQResult:
    complete = _complete_rows(matrix)
    n, k = complete.shape
    if k < 2:
        return CochranQResult(
            q=None,
            degrees_of_freedom=None,
            p_value=None,
            effective_n=n,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            explanation_keys=("cochran_q_requires_two_raters",),
        )
    note_keys = ("two_rater_q_related_to_mcnemar",) if k == 2 else ()
    if n == 0:
        return CochranQResult(
            q=None,
            degrees_of_freedom=k - 1,
            p_value=None,
            effective_n=0,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            explanation_keys=note_keys + ("no_complete_multirater_observations",),
        )
    if n == 1:
        return CochranQResult(
            q=None,
            degrees_of_freedom=k - 1,
            p_value=None,
            effective_n=1,
            status=EstimateStatus.DESCRIPTIVE_ONLY,
            explanation_keys=note_keys + ("one_item_descriptive_only",),
        )

    col = complete.sum(axis=0)
    row = complete.sum(axis=1)
    denominator = float(k * row.sum() - np.square(row).sum())
    if np.isclose(denominator, 0.0):
        return CochranQResult(
            q=None,
            degrees_of_freedom=k - 1,
            p_value=None,
            effective_n=n,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            explanation_keys=note_keys + ("cochran_q_no_discordant_information",),
        )

    numerator = float((k - 1) * (k * np.square(col).sum() - col.sum() ** 2))
    q = numerator / denominator
    p = float(chi2.sf(q, k - 1))
    return CochranQResult(
        q=float(q),
        degrees_of_freedom=k - 1,
        p_value=p,
        effective_n=n,
        status=EstimateStatus.OK,
        explanation_keys=note_keys,
    )


def mcnemar_pair(
    a: np.ndarray,
    b: np.ndarray,
    exact: bool = False,
    *,
    rater_a_id: str = "",
    rater_b_id: str = "",
) -> PairwiseTestResult:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Pairwise vectors must have the same shape")
    mask = ~np.isnan(a) & ~np.isnan(b)
    a = a[mask]
    b = b[mask]
    n = len(a)
    if n == 0:
        return PairwiseTestResult(
            rater_a_id=rater_a_id,
            rater_b_id=rater_b_id,
            statistic=None,
            p_value=None,
            adjusted_p_value=None,
            effective_n=0,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            explanation_keys=("no_complete_pairwise_observations",),
        )
    n00 = int(np.sum((a == 0) & (b == 0)))
    n01 = int(np.sum((a == 0) & (b == 1)))
    n10 = int(np.sum((a == 1) & (b == 0)))
    n11 = int(np.sum((a == 1) & (b == 1)))
    discordant = n01 + n10
    if discordant == 0:
        return PairwiseTestResult(
            rater_a_id=rater_a_id,
            rater_b_id=rater_b_id,
            statistic=None,
            p_value=None,
            adjusted_p_value=None,
            effective_n=n,
            status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
            explanation_keys=("mcnemar_no_discordant_pairs",),
        )
    result = mcnemar([[n00, n01], [n10, n11]], exact=exact, correction=not exact)
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    return PairwiseTestResult(
        rater_a_id=rater_a_id,
        rater_b_id=rater_b_id,
        statistic=statistic,
        p_value=p_value,
        adjusted_p_value=p_value,
        effective_n=n,
        status=EstimateStatus.OK,
    )


def _adjust(values: list[float], correction: str) -> np.ndarray:
    if correction == "none":
        return np.asarray(values, dtype=float)
    method_map = {"holm": "holm", "benjamini-hochberg": "fdr_bh"}
    if correction not in method_map:
        raise ValueError("correction must be one of: none, holm, benjamini-hochberg")
    return np.asarray(multipletests(values, method=method_map[correction])[1], dtype=float)


def posthoc_mcnemar(
    matrix: np.ndarray,
    rater_ids: tuple[str, ...],
    correction: str = "holm",
) -> tuple[PairwiseTestResult, ...]:
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(rater_ids):
        raise ValueError("Matrix columns must match rater_ids")
    results: list[PairwiseTestResult] = []
    for left, right in combinations(range(len(rater_ids)), 2):
        results.append(
            mcnemar_pair(
                values[:, left],
                values[:, right],
                rater_a_id=rater_ids[left],
                rater_b_id=rater_ids[right],
            )
        )

    valid_positions = [index for index, item in enumerate(results) if item.p_value is not None]
    if valid_positions:
        adjusted = _adjust([results[index].p_value for index in valid_positions], correction)
        for position, adjusted_value in zip(valid_positions, adjusted, strict=True):
            item = results[position]
            results[position] = PairwiseTestResult(
                rater_a_id=item.rater_a_id,
                rater_b_id=item.rater_b_id,
                statistic=item.statistic,
                p_value=item.p_value,
                adjusted_p_value=float(adjusted_value),
                effective_n=item.effective_n,
                status=item.status,
                explanation_keys=item.explanation_keys,
            )
    return tuple(results)
