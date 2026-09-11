from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EstimateStatus(StrEnum):
    OK = "ok"
    DESCRIPTIVE_ONLY = "descriptive_only"
    NOT_ESTIMABLE_NO_VARIATION = "not_estimable_no_variation"
    INSUFFICIENT_PAIRED_OBSERVATIONS = "insufficient_paired_observations"
    INCOMPLETE_FOR_METRIC = "incomplete_for_metric"


class AnalysisPerspective(StrEnum):
    NO_REFERENCE = "no_reference"
    REFERENCE_RATER = "reference_rater"
    EXPERT_BENCHMARK = "expert_benchmark"


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric: str
    value: float | None
    status: EstimateStatus
    effective_n: int
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    degrees_of_freedom: int | None = None
    explanation_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PairwiseResult:
    rater_a_id: str
    rater_b_id: str
    raw_agreement: MetricResult
    kappa: MetricResult
    contingency: tuple[tuple[int, int], tuple[int, int]]


@dataclass(frozen=True, slots=True)
class CochranQResult:
    q: float | None
    degrees_of_freedom: int | None
    p_value: float | None
    effective_n: int
    status: EstimateStatus
    explanation_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    confidence_level: float = 0.95
    multiple_testing_correction: str = "holm"
    selected_source_ids: tuple[str, ...] = ()
    selected_categories: tuple[str, ...] = ()
    selected_rater_ids: tuple[str, ...] = ()
    analysis_perspective: AnalysisPerspective = AnalysisPerspective.NO_REFERENCE
    reference_rater_id: str | None = None
    bootstrap_samples: int = 2000
    random_seed: int = 20260905
    category_association_min_occurrences: int = 5


@dataclass(frozen=True, slots=True)
class GroupResult:
    group_id: str
    display_name: str
    lexical_unit_count: int
    pairwise: tuple[PairwiseResult, ...]
    cochran_q: CochranQResult | None
    fleiss_kappa: MetricResult | None = None


@dataclass(frozen=True, slots=True)
class CountSummary:
    lexical_units: int
    raters: int
    total_ratings: int
    metaphor_ratings: int
    non_metaphor_ratings: int
    missing_ratings: int
    category_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class SpecificAgreementResult:
    rater_a_id: str
    rater_b_id: str
    metaphor_agreement: MetricResult
    non_metaphor_agreement: MetricResult


@dataclass(frozen=True, slots=True)
class ExpertBenchmarkResult:
    benchmark_rater_id: str
    rater_id: str
    effective_n: int
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    agreement_with_expert: MetricResult
    sensitivity: MetricResult
    specificity: MetricResult
    precision: MetricResult
    recall: MetricResult


@dataclass(frozen=True, slots=True)
class FreemanHaltonExactResult:
    table_probability: float
    p_value: float


@dataclass(frozen=True, slots=True)
class CategoryAssociationRow:
    category: str
    occurrence_count: int
    metaphor_count: int
    non_metaphor_count: int
    missing_count: int


@dataclass(frozen=True, slots=True)
class RaterCategoryAssociationResult:
    rater_id: str
    rows: tuple[CategoryAssociationRow, ...]
    table_probability: float | None
    p_value: float | None
    adjusted_p_value: float | None
    effective_n: int
    status: EstimateStatus
    explanation_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CategoryAssociationAnalysis:
    min_occurrences: int
    included_categories: tuple[tuple[str, int], ...]
    excluded_categories: tuple[tuple[str, int], ...]
    correction: str
    raters: tuple[RaterCategoryAssociationResult, ...]


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    config: AnalysisConfig
    counts: CountSummary
    pairwise: tuple[PairwiseResult, ...]
    overall_multirater: tuple[MetricResult, ...]
    cochran_q: CochranQResult | None
    posthoc_tendency: tuple[PairwiseTestResult, ...]
    specific_agreement: tuple[SpecificAgreementResult, ...]
    expert_benchmark: tuple[ExpertBenchmarkResult, ...]
    by_category: tuple[GroupResult, ...]
    by_source: tuple[GroupResult, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PairwiseTestResult:
    rater_a_id: str
    rater_b_id: str
    statistic: float | None
    p_value: float | None
    adjusted_p_value: float | None
    effective_n: int
    status: EstimateStatus
    explanation_keys: tuple[str, ...] = ()
