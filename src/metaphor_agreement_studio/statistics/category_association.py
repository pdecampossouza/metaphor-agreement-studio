from __future__ import annotations

from collections import Counter
from dataclasses import replace
from math import comb, prod

from statsmodels.stats.multitest import multipletests

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.types import (
    AnalysisConfig,
    CategoryAssociationAnalysis,
    CategoryAssociationRow,
    EstimateStatus,
    FreemanHaltonExactResult,
    RaterCategoryAssociationResult,
)


def freeman_halton_exact(table: tuple[tuple[int, int], ...]) -> FreemanHaltonExactResult:
    """Return the deterministic two-sided Fisher-Freeman-Halton exact test.

    This implementation is specialized for R x 2 tables. Conditional on the
    observed row and column margins, each feasible table has probability
    proportional to the product of the corresponding binomial coefficients.
    The two-sided p-value sums probabilities no greater than that of the
    observed table, matching the conventional Fisher probability ordering.
    """
    rows = tuple(tuple(int(value) for value in row) for row in table)
    if len(rows) < 2 or any(len(row) != 2 for row in rows):
        raise ValueError("Fisher-Freeman-Halton requires an R x 2 table with at least two rows")
    if any(value < 0 for row in rows for value in row):
        raise ValueError("Contingency counts must be non-negative")

    row_totals = tuple(sum(row) for row in rows)
    if any(total == 0 for total in row_totals):
        raise ValueError("Contingency rows must contain at least one observation")

    total_n = sum(row_totals)
    metaphor_total = sum(row[0] for row in rows)
    denominator = comb(total_n, metaphor_total)
    observed_weight = prod(
        comb(row_total, row[0]) for row_total, row in zip(row_totals, rows, strict=True)
    )
    table_probability = observed_weight / denominator

    # With all observations in one outcome column there is only one feasible
    # conditional table, so the exact p-value is one.
    if metaphor_total in {0, total_n}:
        return FreemanHaltonExactResult(table_probability=1.0, p_value=1.0)

    suffix_capacity = [0] * (len(row_totals) + 1)
    for index in range(len(row_totals) - 1, -1, -1):
        suffix_capacity[index] = suffix_capacity[index + 1] + row_totals[index]

    extreme_weight = 0

    def visit(index: int, remaining: int, partial_weight: int) -> None:
        nonlocal extreme_weight
        if partial_weight > observed_weight:
            return
        if index == len(row_totals) - 1:
            allocated = remaining
            if 0 <= allocated <= row_totals[index]:
                weight = partial_weight * comb(row_totals[index], allocated)
                if weight <= observed_weight:
                    extreme_weight += weight
            return

        minimum = max(0, remaining - suffix_capacity[index + 1])
        maximum = min(row_totals[index], remaining)
        for allocated in range(minimum, maximum + 1):
            visit(
                index + 1,
                remaining - allocated,
                partial_weight * comb(row_totals[index], allocated),
            )

    visit(0, metaphor_total, 1)
    return FreemanHaltonExactResult(
        table_probability=float(table_probability),
        p_value=float(extreme_weight / denominator),
    )


def _selected_source_ids(dataset: ValidatedDataset, config: AnalysisConfig) -> tuple[str, ...]:
    available = tuple(source.source_id for source in dataset.sources)
    if config.selected_source_ids:
        unknown = set(config.selected_source_ids) - set(available)
        if unknown:
            raise ValueError(f"Unknown selected source ids: {sorted(unknown)}")
        selected = set(config.selected_source_ids)
        return tuple(source_id for source_id in available if source_id in selected)
    return tuple(source.source_id for source in dataset.sources if not source.is_aggregate)


def _selected_rater_ids(dataset: ValidatedDataset, config: AnalysisConfig) -> tuple[str, ...]:
    available = tuple(rater.rater_id for rater in dataset.raters)
    if config.selected_rater_ids:
        unknown = set(config.selected_rater_ids) - set(available)
        if unknown:
            raise ValueError(f"Unknown selected rater ids: {sorted(unknown)}")
        selected = set(config.selected_rater_ids)
        return tuple(rater_id for rater_id in available if rater_id in selected)
    return available


def _adjust_p_values(
    results: list[RaterCategoryAssociationResult],
    correction: str,
) -> tuple[RaterCategoryAssociationResult, ...]:
    valid_positions = [index for index, result in enumerate(results) if result.p_value is not None]
    if not valid_positions:
        return tuple(results)

    raw = [results[index].p_value for index in valid_positions]
    values = [float(value) for value in raw if value is not None]
    if correction == "none":
        adjusted = values
    else:
        method = {"holm": "holm", "benjamini-hochberg": "fdr_bh"}.get(correction)
        if method is None:
            raise ValueError("correction must be one of: none, holm, benjamini-hochberg")
        adjusted = [float(value) for value in multipletests(values, method=method)[1]]

    for position, adjusted_value in zip(valid_positions, adjusted, strict=True):
        results[position] = replace(results[position], adjusted_p_value=float(adjusted_value))
    return tuple(results)


def analyze_grammatical_category_association(
    dataset: ValidatedDataset,
    config: AnalysisConfig,
) -> CategoryAssociationAnalysis:
    if not isinstance(dataset, ValidatedDataset):
        raise TypeError("Category association requires a researcher-validated dataset")
    minimum = int(config.category_association_min_occurrences)
    if minimum < 1:
        raise ValueError("category_association_min_occurrences must be at least 1")

    source_ids = set(_selected_source_ids(dataset, config))
    category_filter = set(config.selected_categories)
    scoped_units = tuple(
        unit
        for unit in dataset.units
        if unit.source_id in source_ids
        and (not category_filter or unit.grammatical_category in category_filter)
    )
    occurrence_counts = Counter(unit.grammatical_category for unit in scoped_units)
    included = tuple(
        sorted((category, count) for category, count in occurrence_counts.items() if count >= minimum)
    )
    excluded = tuple(
        sorted((category, count) for category, count in occurrence_counts.items() if count < minimum)
    )
    included_names = {category for category, _ in included}
    scoped_by_id = {unit.unit_id: unit for unit in scoped_units if unit.grammatical_category in included_names}
    annotations = {
        (annotation.unit_id, annotation.rater_id): annotation.classification
        for annotation in dataset.annotations
        if annotation.unit_id in scoped_by_id
    }

    results: list[RaterCategoryAssociationResult] = []
    for rater_id in _selected_rater_ids(dataset, config):
        rows: list[CategoryAssociationRow] = []
        for category, occurrence_count in included:
            category_units = [
                unit for unit in scoped_units if unit.grammatical_category == category
            ]
            values = [annotations.get((unit.unit_id, rater_id), Classification.MISSING) for unit in category_units]
            metaphor_count = sum(value == Classification.METAPHOR for value in values)
            non_metaphor_count = sum(value == Classification.NON_METAPHOR for value in values)
            missing_count = occurrence_count - metaphor_count - non_metaphor_count
            rows.append(
                CategoryAssociationRow(
                    category=category,
                    occurrence_count=occurrence_count,
                    metaphor_count=metaphor_count,
                    non_metaphor_count=non_metaphor_count,
                    missing_count=missing_count,
                )
            )

        observed_rows = [row for row in rows if row.metaphor_count + row.non_metaphor_count > 0]
        effective_n = sum(row.metaphor_count + row.non_metaphor_count for row in rows)
        total_metaphor = sum(row.metaphor_count for row in rows)
        total_non_metaphor = sum(row.non_metaphor_count for row in rows)

        if len(observed_rows) < 2:
            result = RaterCategoryAssociationResult(
                rater_id=rater_id,
                rows=tuple(rows),
                table_probability=None,
                p_value=None,
                adjusted_p_value=None,
                effective_n=effective_n,
                status=EstimateStatus.DESCRIPTIVE_ONLY,
                explanation_keys=("category_association_requires_two_categories",),
            )
        elif total_metaphor == 0 or total_non_metaphor == 0:
            result = RaterCategoryAssociationResult(
                rater_id=rater_id,
                rows=tuple(rows),
                table_probability=None,
                p_value=None,
                adjusted_p_value=None,
                effective_n=effective_n,
                status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
                explanation_keys=("category_association_no_class_variation",),
            )
        else:
            exact = freeman_halton_exact(
                tuple((row.metaphor_count, row.non_metaphor_count) for row in observed_rows)
            )
            result = RaterCategoryAssociationResult(
                rater_id=rater_id,
                rows=tuple(rows),
                table_probability=exact.table_probability,
                p_value=exact.p_value,
                adjusted_p_value=exact.p_value,
                effective_n=effective_n,
                status=EstimateStatus.OK,
            )
        results.append(result)

    return CategoryAssociationAnalysis(
        min_occurrences=minimum,
        included_categories=included,
        excluded_categories=excluded,
        correction=config.multiple_testing_correction,
        raters=_adjust_p_values(results, config.multiple_testing_correction),
    )
