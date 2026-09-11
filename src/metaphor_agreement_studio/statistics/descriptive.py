from __future__ import annotations

from collections import Counter

import numpy as np

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.types import CountSummary, EstimateStatus, MetricResult


def dataset_counts(
    dataset: ValidatedDataset,
    unit_ids: tuple[str, ...] | None = None,
) -> CountSummary:
    selected = set(unit_ids) if unit_ids is not None else {unit.unit_id for unit in dataset.units}
    units = tuple(unit for unit in dataset.units if unit.unit_id in selected)
    raters = tuple(dataset.raters)
    lookup = {
        (annotation.unit_id, annotation.rater_id): annotation.classification
        for annotation in dataset.annotations
        if annotation.unit_id in selected
    }

    metaphor = 0
    non_metaphor = 0
    missing = 0
    for unit in units:
        for rater in raters:
            value = lookup.get((unit.unit_id, rater.rater_id), Classification.MISSING)
            if value == Classification.METAPHOR:
                metaphor += 1
            elif value == Classification.NON_METAPHOR:
                non_metaphor += 1
            else:
                missing += 1

    categories = Counter(unit.grammatical_category for unit in units)
    return CountSummary(
        lexical_units=len(units),
        raters=len(raters),
        total_ratings=len(units) * len(raters),
        metaphor_ratings=metaphor,
        non_metaphor_ratings=non_metaphor,
        missing_ratings=missing,
        category_counts=tuple(sorted(categories.items())),
    )


def raw_pairwise_agreement(a: np.ndarray, b: np.ndarray) -> MetricResult:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Pairwise vectors must have the same shape")
    mask = ~np.isnan(a) & ~np.isnan(b)
    effective_n = int(mask.sum())
    if effective_n == 0:
        return MetricResult(
            metric="raw_agreement",
            value=None,
            status=EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS,
            effective_n=0,
            explanation_keys=("no_complete_pairwise_observations",),
        )
    value = float(np.mean(a[mask] == b[mask]))
    return MetricResult(
        metric="raw_agreement",
        value=value,
        status=EstimateStatus.OK,
        effective_n=effective_n,
    )
