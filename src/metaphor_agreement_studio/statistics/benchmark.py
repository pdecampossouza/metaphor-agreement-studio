from __future__ import annotations

import numpy as np

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.descriptive import raw_pairwise_agreement
from metaphor_agreement_studio.statistics.matrices import pairwise_vectors
from metaphor_agreement_studio.statistics.types import (
    EstimateStatus,
    ExpertBenchmarkResult,
    MetricResult,
)


def _rate_metric(
    metric: str,
    numerator: int,
    denominator: int,
    effective_n: int,
    empty_key: str,
) -> MetricResult:
    if effective_n == 0:
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
            status=EstimateStatus.DESCRIPTIVE_ONLY,
            effective_n=effective_n,
            explanation_keys=(empty_key,),
        )
    return MetricResult(
        metric=metric,
        value=float(numerator / denominator),
        status=EstimateStatus.OK,
        effective_n=effective_n,
    )


def expert_comparison(
    benchmark: np.ndarray,
    observed: np.ndarray,
    *,
    benchmark_rater_id: str,
    rater_id: str,
) -> ExpertBenchmarkResult:
    benchmark = np.asarray(benchmark, dtype=float)
    observed = np.asarray(observed, dtype=float)
    if benchmark.shape != observed.shape:
        raise ValueError("Expert and compared vectors must have the same shape")
    mask = ~np.isnan(benchmark) & ~np.isnan(observed)
    benchmark = benchmark[mask]
    observed = observed[mask]
    effective_n = int(len(benchmark))

    tp = int(np.sum((benchmark == 1) & (observed == 1)))
    tn = int(np.sum((benchmark == 0) & (observed == 0)))
    fp = int(np.sum((benchmark == 0) & (observed == 1)))
    fn = int(np.sum((benchmark == 1) & (observed == 0)))

    agreement = raw_pairwise_agreement(benchmark, observed)
    sensitivity = _rate_metric(
        "expert_sensitivity",
        tp,
        tp + fn,
        effective_n,
        "benchmark_no_positive_cases",
    )
    specificity = _rate_metric(
        "expert_specificity",
        tn,
        tn + fp,
        effective_n,
        "benchmark_no_negative_cases",
    )
    precision = _rate_metric(
        "expert_precision",
        tp,
        tp + fp,
        effective_n,
        "compared_rater_no_positive_predictions",
    )
    recall = MetricResult(
        metric="expert_recall",
        value=sensitivity.value,
        status=sensitivity.status,
        effective_n=sensitivity.effective_n,
        explanation_keys=sensitivity.explanation_keys,
    )
    return ExpertBenchmarkResult(
        benchmark_rater_id=benchmark_rater_id,
        rater_id=rater_id,
        effective_n=effective_n,
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        agreement_with_expert=agreement,
        sensitivity=sensitivity,
        specificity=specificity,
        precision=precision,
        recall=recall,
    )


def expert_benchmark_results(
    dataset: ValidatedDataset,
    benchmark_rater_id: str,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...],
) -> tuple[ExpertBenchmarkResult, ...]:
    results: list[ExpertBenchmarkResult] = []
    for rater_id in rater_ids:
        if rater_id == benchmark_rater_id:
            continue
        vectors = pairwise_vectors(dataset, benchmark_rater_id, rater_id, unit_ids)
        results.append(
            expert_comparison(
                vectors.a,
                vectors.b,
                benchmark_rater_id=benchmark_rater_id,
                rater_id=rater_id,
            )
        )
    return tuple(results)
