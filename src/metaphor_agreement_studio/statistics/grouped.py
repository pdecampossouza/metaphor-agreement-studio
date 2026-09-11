from __future__ import annotations

from itertools import combinations

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.matrices import complete_binary_matrix, pairwise_vectors
from metaphor_agreement_studio.statistics.multirater import fleiss_kappa
from metaphor_agreement_studio.statistics.pairwise import cohen_kappa
from metaphor_agreement_studio.statistics.specific import specific_agreement
from metaphor_agreement_studio.statistics.tendency import cochran_q
from metaphor_agreement_studio.statistics.types import (
    AnalysisConfig,
    AnalysisPerspective,
    GroupResult,
    PairwiseResult,
    SpecificAgreementResult,
)


def ordered_rater_pairs(
    rater_ids: tuple[str, ...],
    config: AnalysisConfig,
) -> tuple[tuple[str, str], ...]:
    if config.analysis_perspective == AnalysisPerspective.NO_REFERENCE:
        return tuple(combinations(rater_ids, 2))
    reference = config.reference_rater_id
    if reference is None or reference not in rater_ids:
        return tuple(combinations(rater_ids, 2))
    others = tuple(rater_id for rater_id in rater_ids if rater_id != reference)
    focused = tuple((reference, rater_id) for rater_id in others)
    return focused + tuple(combinations(others, 2))


def pairwise_results(
    dataset: ValidatedDataset,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...],
    config: AnalysisConfig,
) -> tuple[PairwiseResult, ...]:
    results: list[PairwiseResult] = []
    for rater_a, rater_b in ordered_rater_pairs(rater_ids, config):
        vectors = pairwise_vectors(dataset, rater_a, rater_b, unit_ids)
        results.append(
            cohen_kappa(
                vectors.a,
                vectors.b,
                confidence=config.confidence_level,
                bootstrap_samples=config.bootstrap_samples,
                seed=config.random_seed,
                rater_a_id=rater_a,
                rater_b_id=rater_b,
            )
        )
    return tuple(results)


def specific_results(
    dataset: ValidatedDataset,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...],
    config: AnalysisConfig,
) -> tuple[SpecificAgreementResult, ...]:
    results: list[SpecificAgreementResult] = []
    for rater_a, rater_b in ordered_rater_pairs(rater_ids, config):
        vectors = pairwise_vectors(dataset, rater_a, rater_b, unit_ids)
        results.append(
            specific_agreement(
                vectors.a,
                vectors.b,
                rater_a_id=rater_a,
                rater_b_id=rater_b,
            )
        )
    return tuple(results)


def make_group_result(
    dataset: ValidatedDataset,
    *,
    group_id: str,
    display_name: str,
    unit_ids: tuple[str, ...],
    rater_ids: tuple[str, ...],
    config: AnalysisConfig,
) -> GroupResult:
    q_result = None
    if len(rater_ids) >= 2:
        matrix = complete_binary_matrix(dataset, rater_ids, unit_ids)
        q_result = cochran_q(matrix.values)
    group_fleiss = fleiss_kappa(dataset, rater_ids, unit_ids) if len(rater_ids) >= 3 else None
    return GroupResult(
        group_id=group_id,
        display_name=display_name,
        lexical_unit_count=len(unit_ids),
        pairwise=pairwise_results(dataset, rater_ids, unit_ids, config),
        cochran_q=q_result,
        fleiss_kappa=group_fleiss,
    )
