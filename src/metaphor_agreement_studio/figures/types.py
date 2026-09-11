from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


class FigureKind(StrEnum):
    AGREEMENT_FINGERPRINT = "agreement_fingerprint"
    PAIRWISE_KAPPA_MATRIX = "pairwise_kappa_matrix"
    AGREEMENT_BY_CATEGORY = "agreement_by_category"
    AGREEMENT_VS_SAMPLE_SIZE = "agreement_vs_sample_size"
    METAPHOR_RATE_BY_RATER = "metaphor_rate_by_rater"
    DISAGREEMENT_BY_CATEGORY = "disagreement_by_category"
    RATER_DIVERGENCE = "rater_divergence"
    MULTI_RATER_PATTERNS = "multi_rater_patterns"
    SOURCE_COMPARISON = "source_comparison"
    SPECIFIC_AGREEMENT = "specific_agreement"
    REVIEW_DENSITY = "review_density"


SEMANTIC_MARKERS: Mapping[str, str] = {
    "Metaphor": "circle",
    "Non-metaphor": "x",
    "Missing": "circle-open",
    "Review": "diamond",
}


@dataclass(frozen=True, slots=True)
class FigureSpec:
    kind: FigureKind
    title: str
    subtitle: str = ""
    rater_pair: tuple[str, str] | None = None
    size_preset: str = "double-column"
    filters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FigureProvenance:
    project_name: str
    dataset_version: str
    analysis_version: str
    raters: tuple[str, ...]
    filters: Mapping[str, Any]
    software_version: str
    generated_at: str
    dataset_content_hash: str | None = None
    analysis_config_hash: str | None = None


@dataclass(frozen=True, slots=True)
class FigureDataset:
    kind: FigureKind
    frame: pd.DataFrame
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExportedFigure:
    figure_path: Path
    provenance_path: Path
    format: str
    dpi: int | None
