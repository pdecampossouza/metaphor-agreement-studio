from __future__ import annotations

import numpy as np

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.benchmark import expert_benchmark_results
from metaphor_agreement_studio.statistics.descriptive import dataset_counts
from metaphor_agreement_studio.statistics.grouped import (
    make_group_result,
    pairwise_results,
    specific_results,
)
from metaphor_agreement_studio.statistics.matrices import complete_binary_matrix
from metaphor_agreement_studio.statistics.multirater import fleiss_kappa, krippendorff_alpha
from metaphor_agreement_studio.statistics.tendency import cochran_q, posthoc_mcnemar
from metaphor_agreement_studio.statistics.types import (
    AnalysisBundle,
    AnalysisConfig,
    AnalysisPerspective,
    CountSummary,
)


def _selected_raters(dataset: ValidatedDataset, config: AnalysisConfig) -> tuple[str, ...]:
    available = tuple(rater.rater_id for rater in dataset.raters)
    if not config.selected_rater_ids:
        return available
    unknown = set(config.selected_rater_ids) - set(available)
    if unknown:
        raise ValueError(f"Unknown selected rater ids: {sorted(unknown)}")
    selected = set(config.selected_rater_ids)
    return tuple(rater_id for rater_id in available if rater_id in selected)


def _overall_source_ids(dataset: ValidatedDataset, config: AnalysisConfig) -> tuple[str, ...]:
    available = tuple(source.source_id for source in dataset.sources)
    if config.selected_source_ids:
        unknown = set(config.selected_source_ids) - set(available)
        if unknown:
            raise ValueError(f"Unknown selected source ids: {sorted(unknown)}")
        selected = set(config.selected_source_ids)
        return tuple(source_id for source_id in available if source_id in selected)
    return tuple(source.source_id for source in dataset.sources if not source.is_aggregate)


def _unit_ids_for_sources(
    dataset: ValidatedDataset,
    source_ids: tuple[str, ...],
    categories: tuple[str, ...],
) -> tuple[str, ...]:
    source_set = set(source_ids)
    category_set = set(categories)
    return tuple(
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in source_set
        and (not category_set or unit.grammatical_category in category_set)
    )


def _counts_for_selected_raters(
    dataset: ValidatedDataset,
    unit_ids: tuple[str, ...],
    rater_ids: tuple[str, ...],
) -> CountSummary:
    base = dataset_counts(dataset, unit_ids)
    if len(rater_ids) == len(dataset.raters):
        return base
    unit_set = set(unit_ids)
    rater_set = set(rater_ids)
    selected_annotations = [
        annotation
        for annotation in dataset.annotations
        if annotation.unit_id in unit_set and annotation.rater_id in rater_set
    ]
    metaphor = sum(annotation.classification.value == "METAPHOR" for annotation in selected_annotations)
    non_metaphor = sum(
        annotation.classification.value == "NON_METAPHOR" for annotation in selected_annotations
    )
    total = len(unit_ids) * len(rater_ids)
    missing = total - metaphor - non_metaphor
    return CountSummary(
        lexical_units=base.lexical_units,
        raters=len(rater_ids),
        total_ratings=total,
        metaphor_ratings=metaphor,
        non_metaphor_ratings=non_metaphor,
        missing_ratings=missing,
        category_counts=base.category_counts,
    )


def _warning_keys(matrix: np.ndarray) -> tuple[str, ...]:
    warnings: list[str] = []
    observed = matrix[~np.isnan(matrix)]
    if len(observed):
        positives = int(np.sum(observed == 1))
        negatives = int(np.sum(observed == 0))
        majority = max(positives, negatives) / len(observed)
        if majority >= 0.90:
            warnings.append("class_imbalance_kappa_prevalence")
    if np.isnan(matrix).any():
        warnings.append("missing_annotations_present")
    return tuple(warnings)


def analyze_dataset(dataset: ValidatedDataset, config: AnalysisConfig) -> AnalysisBundle:
    if not isinstance(dataset, ValidatedDataset):
        raise TypeError("analyze_dataset requires a ValidatedDataset produced by researcher validation")

    rater_ids = _selected_raters(dataset, config)
    source_ids = _overall_source_ids(dataset, config)
    overall_unit_ids = _unit_ids_for_sources(dataset, source_ids, config.selected_categories)
    counts = _counts_for_selected_raters(dataset, overall_unit_ids, rater_ids)

    if config.analysis_perspective != AnalysisPerspective.NO_REFERENCE:
        if config.reference_rater_id is None:
            raise ValueError("This analysis perspective requires a reference rater")
        available_raters = {rater.rater_id for rater in dataset.raters}
        if config.reference_rater_id not in available_raters:
            raise ValueError(f"Unknown reference rater: {config.reference_rater_id}")
        if config.reference_rater_id not in rater_ids:
            raise ValueError("The reference rater must be included among selected raters")

    pairwise = pairwise_results(dataset, rater_ids, overall_unit_ids, config)
    specific = specific_results(dataset, rater_ids, overall_unit_ids, config)

    overall_matrix = complete_binary_matrix(dataset, rater_ids, overall_unit_ids)
    q_result = cochran_q(overall_matrix.values) if len(rater_ids) >= 2 else None
    posthoc = (
        posthoc_mcnemar(
            overall_matrix.values,
            rater_ids,
            correction=config.multiple_testing_correction,
        )
        if len(rater_ids) >= 2
        else ()
    )

    multi = ()
    if len(rater_ids) >= 3:
        multi = (
            fleiss_kappa(dataset, rater_ids, overall_unit_ids),
            krippendorff_alpha(dataset, rater_ids, overall_unit_ids),
        )

    category_names = sorted(
        {unit.grammatical_category for unit in dataset.units if unit.unit_id in set(overall_unit_ids)}
    )
    by_category = tuple(
        make_group_result(
            dataset,
            group_id=category,
            display_name=category,
            unit_ids=tuple(
                unit.unit_id
                for unit in dataset.units
                if unit.unit_id in set(overall_unit_ids)
                and unit.grammatical_category == category
            ),
            rater_ids=rater_ids,
            config=config,
        )
        for category in category_names
    )

    if config.selected_source_ids:
        group_source_ids = source_ids
    else:
        group_source_ids = tuple(source.source_id for source in dataset.sources)
    source_lookup = {source.source_id: source for source in dataset.sources}
    by_source = tuple(
        make_group_result(
            dataset,
            group_id=source_id,
            display_name=source_lookup[source_id].display_name,
            unit_ids=_unit_ids_for_sources(dataset, (source_id,), config.selected_categories),
            rater_ids=rater_ids,
            config=config,
        )
        for source_id in group_source_ids
    )

    expert = ()
    if config.analysis_perspective == AnalysisPerspective.EXPERT_BENCHMARK:
        expert = expert_benchmark_results(
            dataset,
            config.reference_rater_id or "",
            rater_ids,
            overall_unit_ids,
        )

    return AnalysisBundle(
        config=config,
        counts=counts,
        pairwise=pairwise,
        overall_multirater=multi,
        cochran_q=q_result,
        posthoc_tendency=posthoc,
        specific_agreement=specific,
        expert_benchmark=expert,
        by_category=by_category,
        by_source=by_source,
        warnings=_warning_keys(overall_matrix.values),
    )

_CACHED_ANALYZE = None


def analyze_dataset_cached(dataset: ValidatedDataset, config: AnalysisConfig) -> AnalysisBundle:
    """Streamlit cache wrapper keyed by canonical dataset content plus normalized analysis settings."""
    global _CACHED_ANALYZE
    from metaphor_agreement_studio.common.cache_keys import analysis_cache_key

    if _CACHED_ANALYZE is None:
        import streamlit as st

        @st.cache_data(show_spinner=False)
        def _cached(cache_key: str, _dataset: ValidatedDataset, _config: AnalysisConfig) -> AnalysisBundle:
            del cache_key
            return analyze_dataset(_dataset, _config)

        _CACHED_ANALYZE = _cached
    return _CACHED_ANALYZE(analysis_cache_key(dataset, config), dataset, config)
