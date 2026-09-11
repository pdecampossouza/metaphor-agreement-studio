from __future__ import annotations

from collections import Counter
from itertools import combinations
import math

import pandas as pd

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind
from metaphor_agreement_studio.statistics.types import AnalysisBundle, GroupResult, PairwiseResult


def _pair_for_group(group: GroupResult, rater_pair: tuple[str, str]) -> PairwiseResult | None:
    wanted = frozenset(rater_pair)
    return next(
        (item for item in group.pairwise if frozenset((item.rater_a_id, item.rater_b_id)) == wanted),
        None,
    )


def _group_rows(
    groups: tuple[GroupResult, ...],
    *,
    label_column: str,
    rater_pair: tuple[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in groups:
        pair = _pair_for_group(group, rater_pair)
        if pair is None:
            rows.append(
                {
                    label_column: group.display_name,
                    "group_id": group.group_id,
                    "n": group.lexical_unit_count,
                    "estimate": math.nan,
                    "ci_low": math.nan,
                    "ci_high": math.nan,
                    "raw_agreement": math.nan,
                    "status": "not_available",
                }
            )
            continue
        rows.append(
            {
                label_column: group.display_name,
                "group_id": group.group_id,
                "n": group.lexical_unit_count,
                "estimate": pair.kappa.value,
                "ci_low": pair.kappa.ci_low,
                "ci_high": pair.kappa.ci_high,
                "raw_agreement": pair.raw_agreement.value,
                "status": pair.kappa.status.value,
            }
        )
    return rows


def build_category_agreement_data(
    analysis_bundle: AnalysisBundle,
    rater_pair: tuple[str, str],
) -> FigureDataset:
    frame = pd.DataFrame(
        _group_rows(analysis_bundle.by_category, label_column="category", rater_pair=rater_pair)
    )
    return FigureDataset(FigureKind.AGREEMENT_BY_CATEGORY, frame, {"rater_pair": rater_pair})


def build_agreement_vs_sample_size_data(
    analysis_bundle: AnalysisBundle,
    rater_pair: tuple[str, str],
) -> FigureDataset:
    base = build_category_agreement_data(analysis_bundle, rater_pair)
    return FigureDataset(FigureKind.AGREEMENT_VS_SAMPLE_SIZE, base.frame.copy(), base.metadata)


def build_source_comparison_data(
    analysis_bundle: AnalysisBundle,
    rater_pair: tuple[str, str],
) -> FigureDataset:
    frame = pd.DataFrame(
        _group_rows(analysis_bundle.by_source, label_column="source", rater_pair=rater_pair)
    )
    return FigureDataset(FigureKind.SOURCE_COMPARISON, frame, {"rater_pair": rater_pair})


def build_pairwise_kappa_matrix_data(
    analysis_bundle: AnalysisBundle, dataset: ValidatedDataset | None = None
) -> FigureDataset:
    raters: list[str] = []
    for item in analysis_bundle.pairwise:
        for rater_id in (item.rater_a_id, item.rater_b_id):
            if rater_id not in raters:
                raters.append(rater_id)
    if not raters:
        raters = list(analysis_bundle.config.selected_rater_ids)
    rater_lookup = (
        {rater.rater_id: rater.display_name for rater in dataset.raters}
        if dataset is not None
        else {}
    )
    lookup: dict[frozenset[str], PairwiseResult] = {
        frozenset((item.rater_a_id, item.rater_b_id)): item for item in analysis_bundle.pairwise
    }
    rows: list[dict[str, object]] = []
    for rater_a in raters:
        for rater_b in raters:
            if rater_a == rater_b:
                rows.append(
                    {
                        "rater_a_id": rater_a,
                        "rater_b_id": rater_b,
                        "rater_a": rater_lookup.get(rater_a, rater_a),
                        "rater_b": rater_lookup.get(rater_b, rater_b),
                        "estimate": math.nan,
                        "raw_agreement": math.nan,
                        "n": math.nan,
                        "ci_low": math.nan,
                        "ci_high": math.nan,
                        "status": "diagonal",
                    }
                )
                continue
            pair = lookup.get(frozenset((rater_a, rater_b)))
            rows.append(
                {
                    "rater_a_id": rater_a,
                    "rater_b_id": rater_b,
                    "rater_a": rater_lookup.get(rater_a, rater_a),
                    "rater_b": rater_lookup.get(rater_b, rater_b),
                    "estimate": pair.kappa.value if pair else math.nan,
                    "raw_agreement": pair.raw_agreement.value if pair else math.nan,
                    "n": pair.kappa.effective_n if pair else math.nan,
                    "ci_low": pair.kappa.ci_low if pair else math.nan,
                    "ci_high": pair.kappa.ci_high if pair else math.nan,
                    "status": pair.kappa.status.value if pair else "not_available",
                }
            )
    return FigureDataset(
        FigureKind.PAIRWISE_KAPPA_MATRIX,
        pd.DataFrame(rows),
        {"raters": tuple(rater_lookup.get(rater_id, rater_id) for rater_id in raters), "rater_ids": tuple(raters)},
    )


def _selected_unit_ids(dataset: ValidatedDataset, bundle: AnalysisBundle) -> tuple[str, ...]:
    config = bundle.config
    if config.selected_source_ids:
        source_ids = set(config.selected_source_ids)
    else:
        source_ids = {source.source_id for source in dataset.sources if not source.is_aggregate}
    categories = set(config.selected_categories)
    return tuple(
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in source_ids and (not categories or unit.grammatical_category in categories)
    )


def _selected_raters(dataset: ValidatedDataset, bundle: AnalysisBundle) -> tuple[str, ...]:
    if bundle.config.selected_rater_ids:
        return tuple(bundle.config.selected_rater_ids)
    return tuple(rater.rater_id for rater in dataset.raters)


def build_agreement_fingerprint_data(dataset: ValidatedDataset, bundle: AnalysisBundle) -> FigureDataset:
    unit_ids = set(_selected_unit_ids(dataset, bundle))
    rater_ids = _selected_raters(dataset, bundle)
    unit_lookup = {unit.unit_id: unit for unit in dataset.units if unit.unit_id in unit_ids}
    source_lookup = {source.source_id: source.display_name for source in dataset.sources}
    annotation_lookup = {(a.unit_id, a.rater_id): a for a in dataset.annotations}
    rater_lookup = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for unit in dataset.units:
        if unit.unit_id not in unit_ids:
            continue
        values = [annotation_lookup.get((unit.unit_id, rid)) for rid in rater_ids]
        classes = [a.classification.value if a else Classification.MISSING.value for a in values]
        non_missing = [value for value in classes if value != Classification.MISSING.value]
        disagreement = len(set(non_missing)) > 1
        for rater_id, annotation in zip(rater_ids, values, strict=True):
            classification = annotation.classification if annotation else Classification.MISSING
            label = {
                Classification.METAPHOR: "Metaphor",
                Classification.NON_METAPHOR: "Non-metaphor",
                Classification.MISSING: "Missing",
            }[classification]
            rows.append(
                {
                    "unit_id": unit.unit_id,
                    "lexical_unit": unit.lexical_unit,
                    "category": unit.grammatical_category,
                    "source": source_lookup.get(unit.source_id, unit.source_id),
                    "occurrence_index": unit.occurrence_index,
                    "rater_id": rater_id,
                    "rater": rater_lookup.get(rater_id, rater_id),
                    "classification": label,
                    "requires_review": disagreement,
                }
            )
    return FigureDataset(
        FigureKind.AGREEMENT_FINGERPRINT,
        pd.DataFrame(rows),
        {"raters": tuple(rater_lookup.get(rater_id, rater_id) for rater_id in rater_ids), "rater_ids": rater_ids},
    )


def build_metaphor_rate_by_rater_data(dataset: ValidatedDataset, bundle: AnalysisBundle) -> FigureDataset:
    unit_ids = set(_selected_unit_ids(dataset, bundle))
    rater_ids = _selected_raters(dataset, bundle)
    rater_lookup = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for rater_id in rater_ids:
        ratings = [
            a.classification
            for a in dataset.annotations
            if a.rater_id == rater_id and a.unit_id in unit_ids and a.classification != Classification.MISSING
        ]
        n = len(ratings)
        positives = sum(value == Classification.METAPHOR for value in ratings)
        rows.append(
            {
                "rater_id": rater_id,
                "rater": rater_lookup.get(rater_id, rater_id),
                "metaphor_count": positives,
                "n": n,
                "rate": positives / n if n else math.nan,
            }
        )
    return FigureDataset(FigureKind.METAPHOR_RATE_BY_RATER, pd.DataFrame(rows))


def _unit_consensus_rows(dataset: ValidatedDataset, bundle: AnalysisBundle) -> list[dict[str, object]]:
    unit_ids = set(_selected_unit_ids(dataset, bundle))
    rater_ids = _selected_raters(dataset, bundle)
    unit_lookup = {unit.unit_id: unit for unit in dataset.units}
    source_lookup = {source.source_id: source.display_name for source in dataset.sources}
    ann_lookup = {(a.unit_id, a.rater_id): a.classification for a in dataset.annotations}
    rows: list[dict[str, object]] = []
    for unit_id in unit_ids:
        unit = unit_lookup[unit_id]
        classes = [ann_lookup.get((unit_id, rater_id), Classification.MISSING) for rater_id in rater_ids]
        observed = [value for value in classes if value != Classification.MISSING]
        disagreement = len(set(observed)) > 1
        rows.append(
            {
                "unit_id": unit_id,
                "category": unit.grammatical_category,
                "source": source_lookup.get(unit.source_id, unit.source_id),
                "disagreement": disagreement,
                "rated_n": len(observed),
                "rater_n": len(rater_ids),
            }
        )
    return rows


def build_disagreement_by_category_data(dataset: ValidatedDataset, bundle: AnalysisBundle) -> FigureDataset:
    base = pd.DataFrame(_unit_consensus_rows(dataset, bundle))
    rows: list[dict[str, object]] = []
    if not base.empty:
        for category, group in base.groupby("category", sort=True):
            disagreement_cases = int(group["disagreement"].sum())
            n = len(group)
            rows.append({"category": category, "disagreement_cases": disagreement_cases, "n": n, "rate": disagreement_cases / n})
    return FigureDataset(FigureKind.DISAGREEMENT_BY_CATEGORY, pd.DataFrame(rows))


def build_review_density_data(dataset: ValidatedDataset, bundle: AnalysisBundle) -> FigureDataset:
    base = pd.DataFrame(_unit_consensus_rows(dataset, bundle))
    rows: list[dict[str, object]] = []
    if not base.empty:
        for (source, category), group in base.groupby(["source", "category"], sort=True):
            disagreement_cases = int(group["disagreement"].sum())
            n = len(group)
            rows.append(
                {
                    "source": source,
                    "category": category,
                    "disagreement_cases": disagreement_cases,
                    "n": n,
                    "rate": disagreement_cases / n,
                }
            )
    return FigureDataset(FigureKind.REVIEW_DENSITY, pd.DataFrame(rows))


def build_rater_divergence_data(
    analysis_bundle: AnalysisBundle, dataset: ValidatedDataset | None = None
) -> FigureDataset:
    raters: set[str] = set()
    scores: dict[str, list[float]] = {}
    for pair in analysis_bundle.pairwise:
        for rater_id in (pair.rater_a_id, pair.rater_b_id):
            raters.add(rater_id)
        if pair.kappa.value is not None:
            scores.setdefault(pair.rater_a_id, []).append(pair.kappa.value)
            scores.setdefault(pair.rater_b_id, []).append(pair.kappa.value)
    rater_lookup = (
        {rater.rater_id: rater.display_name for rater in dataset.raters}
        if dataset is not None
        else {}
    )
    rows = [
        {
            "rater_id": rater_id,
            "rater": rater_lookup.get(rater_id, rater_id),
            "mean_pairwise_kappa": sum(scores.get(rater_id, [])) / len(scores[rater_id])
            if scores.get(rater_id)
            else math.nan,
            "comparisons": len(scores.get(rater_id, [])),
        }
        for rater_id in sorted(raters)
    ]
    return FigureDataset(FigureKind.RATER_DIVERGENCE, pd.DataFrame(rows))


def build_specific_agreement_data(
    analysis_bundle: AnalysisBundle, dataset: ValidatedDataset | None = None
) -> FigureDataset:
    rater_lookup = (
        {rater.rater_id: rater.display_name for rater in dataset.raters}
        if dataset is not None
        else {}
    )
    rows: list[dict[str, object]] = []
    for item in analysis_bundle.specific_agreement:
        rows.extend(
            [
                {
                    "rater_a_id": item.rater_a_id,
                    "rater_b_id": item.rater_b_id,
                    "rater_a": rater_lookup.get(item.rater_a_id, item.rater_a_id),
                    "rater_b": rater_lookup.get(item.rater_b_id, item.rater_b_id),
                    "classification": "Metaphor",
                    "estimate": item.metaphor_agreement.value,
                    "n": item.metaphor_agreement.effective_n,
                    "status": item.metaphor_agreement.status.value,
                },
                {
                    "rater_a_id": item.rater_a_id,
                    "rater_b_id": item.rater_b_id,
                    "rater_a": rater_lookup.get(item.rater_a_id, item.rater_a_id),
                    "rater_b": rater_lookup.get(item.rater_b_id, item.rater_b_id),
                    "classification": "Non-metaphor",
                    "estimate": item.non_metaphor_agreement.value,
                    "n": item.non_metaphor_agreement.effective_n,
                    "status": item.non_metaphor_agreement.status.value,
                },
            ]
        )
    return FigureDataset(FigureKind.SPECIFIC_AGREEMENT, pd.DataFrame(rows))


def build_multi_rater_patterns_data(dataset: ValidatedDataset, bundle: AnalysisBundle) -> FigureDataset:
    unit_ids = set(_selected_unit_ids(dataset, bundle))
    raters = _selected_raters(dataset, bundle)
    ann = {(a.unit_id, a.rater_id): a.classification for a in dataset.annotations}
    counts: Counter[tuple[str, ...]] = Counter()
    for unit_id in unit_ids:
        metaphor_raters = tuple(
            rater_id
            for rater_id in raters
            if ann.get((unit_id, rater_id), Classification.MISSING) == Classification.METAPHOR
        )
        counts[metaphor_raters] += 1
    rater_lookup = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows = [
        {
            "pattern": " + ".join(rater_lookup.get(rater_id, rater_id) for rater_id in pattern)
            if pattern
            else "None",
            "count": count,
            "raters": tuple(rater_lookup.get(rater_id, rater_id) for rater_id in pattern),
            "rater_ids": pattern,
        }
        for pattern, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return FigureDataset(
        FigureKind.MULTI_RATER_PATTERNS,
        pd.DataFrame(rows),
        {
            "raters": tuple(rater_lookup.get(rater_id, rater_id) for rater_id in raters),
            "rater_ids": raters,
        },
    )


def sort_fingerprint_data(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Order fingerprint rows by lexical occurrence while preserving rater order within each unit."""
    if frame.empty:
        return frame.copy()
    valid_modes = {"Source order", "Grammatical category", "Most disagreement first"}
    if mode not in valid_modes:
        raise ValueError(f"Unknown fingerprint sort mode: {mode}")
    work = frame.copy().reset_index(drop=True)
    work["__row_order"] = range(len(work))
    units = work.drop_duplicates("unit_id").copy()
    units["__original_unit_order"] = range(len(units))
    if mode == "Source order":
        units = units.sort_values(["source", "__original_unit_order"], kind="stable")
    elif mode == "Grammatical category":
        units = units.sort_values(
            ["category", "source", "__original_unit_order"], kind="stable"
        )
    else:
        units = units.sort_values(
            ["requires_review", "source", "__original_unit_order"],
            ascending=[False, True, True],
            kind="stable",
        )
    rank = {unit_id: idx for idx, unit_id in enumerate(units["unit_id"])}
    work["__unit_rank"] = work["unit_id"].map(rank)
    work = work.sort_values(["__unit_rank", "__row_order"], kind="stable")
    return work.drop(columns=["__row_order", "__unit_rank"]).reset_index(drop=True)
