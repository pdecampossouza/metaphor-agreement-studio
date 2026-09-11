from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from metaphor_agreement_studio.domain.enums import Classification


class ReviewStatus(StrEnum):
    DISAGREEMENT = "disagreement"
    UNANIMOUS_METAPHOR = "unanimous_metaphor"
    UNANIMOUS_NON_METAPHOR = "unanimous_non_metaphor"
    NO_AVAILABLE_RATINGS = "no_available_ratings"


@dataclass(frozen=True, slots=True)
class ReviewCase:
    unit_id: str
    lexical_unit: str
    grammatical_category: str
    source_id: str
    source_display_name: str
    status: ReviewStatus
    rater_classifications: tuple[tuple[str, Classification], ...]
    metaphor_count: int
    non_metaphor_count: int
    missing_count: int
    agreement_fraction: float | None
    majority_classification: Classification | None
    adjudicated_classification: Classification | None
    divergent_rater_ids: tuple[str, ...]
    context: str | None = None
    verse: str | None = None

    @property
    def has_missing(self) -> bool:
        return self.missing_count > 0

    @property
    def available_ratings(self) -> int:
        return self.metaphor_count + self.non_metaphor_count


@dataclass(frozen=True, slots=True)
class RaterProfile:
    focus_rater_id: str
    metaphor_rate: float
    non_metaphor_rate: float
    missing_rate: float
    mean_pairwise_kappa: float | None
    differs_from_all_count: int
    agrees_with_majority_count: int
    total_units: int
