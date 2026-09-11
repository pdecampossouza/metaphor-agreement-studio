from __future__ import annotations

from collections import defaultdict

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.review.types import RaterProfile, ReviewCase, ReviewStatus
from metaphor_agreement_studio.statistics.types import AnalysisBundle, EstimateStatus


def _selected_rater_ids(
    dataset: ValidatedDataset,
    selected_raters: tuple[str, ...] | None,
) -> tuple[str, ...]:
    available = tuple(rater.rater_id for rater in dataset.raters)
    if selected_raters is None:
        return available
    unknown = set(selected_raters) - set(available)
    if unknown:
        raise ValueError(f"Unknown selected rater ids: {sorted(unknown)}")
    selected = set(selected_raters)
    return tuple(rater_id for rater_id in available if rater_id in selected)


def _status(metaphor: int, non_metaphor: int) -> ReviewStatus:
    if metaphor and non_metaphor:
        return ReviewStatus.DISAGREEMENT
    if metaphor:
        return ReviewStatus.UNANIMOUS_METAPHOR
    if non_metaphor:
        return ReviewStatus.UNANIMOUS_NON_METAPHOR
    return ReviewStatus.NO_AVAILABLE_RATINGS


def _majority(metaphor: int, non_metaphor: int) -> Classification | None:
    available = metaphor + non_metaphor
    if not available:
        return None
    if metaphor > available / 2:
        return Classification.METAPHOR
    if non_metaphor > available / 2:
        return Classification.NON_METAPHOR
    return None


def build_review_cases(
    dataset: ValidatedDataset,
    selected_raters: tuple[str, ...] | None = None,
    unit_ids: tuple[str, ...] | None = None,
) -> tuple[ReviewCase, ...]:
    rater_ids = _selected_rater_ids(dataset, selected_raters)
    unit_filter = set(unit_ids) if unit_ids is not None else None
    source_names = {source.source_id: source.display_name for source in dataset.sources}
    by_unit: dict[str, dict[str, Classification]] = defaultdict(dict)
    for annotation in dataset.annotations:
        if annotation.rater_id in rater_ids and (
            unit_filter is None or annotation.unit_id in unit_filter
        ):
            by_unit[annotation.unit_id][annotation.rater_id] = annotation.classification

    unit_order = {unit.unit_id: index for index, unit in enumerate(dataset.units)}
    cases: list[ReviewCase] = []
    for unit in dataset.units:
        if unit_filter is not None and unit.unit_id not in unit_filter:
            continue
        classifications = tuple(
            (
                rater_id,
                by_unit.get(unit.unit_id, {}).get(rater_id, Classification.MISSING),
            )
            for rater_id in rater_ids
        )
        metaphor = sum(value is Classification.METAPHOR for _, value in classifications)
        non_metaphor = sum(value is Classification.NON_METAPHOR for _, value in classifications)
        missing = len(classifications) - metaphor - non_metaphor
        available = metaphor + non_metaphor
        majority = _majority(metaphor, non_metaphor)
        agreement_fraction = None if not available else max(metaphor, non_metaphor) / available
        divergent = tuple(
            rater_id
            for rater_id, classification in classifications
            if majority is not None
            and classification is not Classification.MISSING
            and classification is not majority
        )
        cases.append(
            ReviewCase(
                unit_id=unit.unit_id,
                lexical_unit=unit.lexical_unit,
                grammatical_category=unit.grammatical_category,
                source_id=unit.source_id,
                source_display_name=source_names.get(unit.source_id, unit.source_id),
                status=_status(metaphor, non_metaphor),
                rater_classifications=classifications,
                metaphor_count=metaphor,
                non_metaphor_count=non_metaphor,
                missing_count=missing,
                agreement_fraction=agreement_fraction,
                majority_classification=majority,
                adjudicated_classification=None,
                divergent_rater_ids=divergent,
                context=unit.context,
                verse=unit.verse,
            )
        )

    status_rank = {
        ReviewStatus.DISAGREEMENT: 0,
        ReviewStatus.NO_AVAILABLE_RATINGS: 1,
        ReviewStatus.UNANIMOUS_METAPHOR: 2,
        ReviewStatus.UNANIMOUS_NON_METAPHOR: 2,
    }
    cases.sort(
        key=lambda case: (
            status_rank[case.status],
            0 if case.has_missing else 1,
            1.0 if case.agreement_fraction is None else case.agreement_fraction,
            unit_order[case.unit_id],
        )
    )
    return tuple(cases)


def build_rater_profile(
    dataset: ValidatedDataset,
    focus_rater_id: str,
    analysis_bundle: AnalysisBundle,
) -> RaterProfile:
    rater_ids = {rater.rater_id for rater in dataset.raters}
    if focus_rater_id not in rater_ids:
        raise ValueError(f"Unknown focus rater: {focus_rater_id}")

    config = analysis_bundle.config
    source_ids = (
        set(config.selected_source_ids)
        if config.selected_source_ids
        else {source.source_id for source in dataset.sources if not source.is_aggregate}
    )
    categories = set(config.selected_categories)
    unit_ids = tuple(
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in source_ids
        and (not categories or unit.grammatical_category in categories)
    )
    unit_set = set(unit_ids)
    values = [
        annotation.classification
        for annotation in dataset.annotations
        if annotation.rater_id == focus_rater_id and annotation.unit_id in unit_set
    ]
    total = len(unit_ids)
    metaphor = sum(value is Classification.METAPHOR for value in values)
    non_metaphor = sum(value is Classification.NON_METAPHOR for value in values)
    missing = max(0, total - metaphor - non_metaphor)

    kappas = [
        pair.kappa.value
        for pair in analysis_bundle.pairwise
        if focus_rater_id in (pair.rater_a_id, pair.rater_b_id)
        and pair.kappa.status is EstimateStatus.OK
        and pair.kappa.value is not None
    ]
    mean_kappa = None if not kappas else sum(kappas) / len(kappas)

    selected_raters = config.selected_rater_ids or None
    cases = build_review_cases(dataset, selected_raters=selected_raters, unit_ids=unit_ids)
    classification_by_unit = {
        annotation.unit_id: annotation.classification
        for annotation in dataset.annotations
        if annotation.rater_id == focus_rater_id
    }
    differs_from_all = 0
    agrees_with_majority = 0
    for case in cases:
        focus_value = classification_by_unit.get(case.unit_id, Classification.MISSING)
        available_others = [
            value
            for rater_id, value in case.rater_classifications
            if rater_id != focus_rater_id and value is not Classification.MISSING
        ]
        if (
            focus_value is not Classification.MISSING
            and available_others
            and all(value is not focus_value for value in available_others)
        ):
            differs_from_all += 1
        if case.majority_classification is not None and focus_value is case.majority_classification:
            agrees_with_majority += 1

    denominator = total or 1
    return RaterProfile(
        focus_rater_id=focus_rater_id,
        metaphor_rate=metaphor / denominator,
        non_metaphor_rate=non_metaphor / denominator,
        missing_rate=missing / denominator,
        mean_pairwise_kappa=mean_kappa,
        differs_from_all_count=differs_from_all,
        agrees_with_majority_count=agrees_with_majority,
        total_units=total,
    )
