from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset


@dataclass(frozen=True, slots=True)
class PairwiseVectors:
    a: np.ndarray
    b: np.ndarray
    unit_ids: tuple[str, ...]

    @property
    def effective_n(self) -> int:
        return len(self.unit_ids)


@dataclass(frozen=True, slots=True)
class BinaryMatrix:
    values: np.ndarray
    unit_ids: tuple[str, ...]
    rater_ids: tuple[str, ...]

    @property
    def complete_row_mask(self) -> np.ndarray:
        return ~np.isnan(self.values).any(axis=1)

    @property
    def effective_n(self) -> int:
        return int(self.complete_row_mask.sum())


def _encode(classification: Classification) -> float:
    if classification == Classification.METAPHOR:
        return 1.0
    if classification == Classification.NON_METAPHOR:
        return 0.0
    return float("nan")


def _selected_unit_ids(dataset: ValidatedDataset, unit_ids: tuple[str, ...] | None) -> tuple[str, ...]:
    available = {unit.unit_id for unit in dataset.units}
    if unit_ids is None:
        return tuple(unit.unit_id for unit in dataset.units)
    unknown = set(unit_ids) - available
    if unknown:
        raise ValueError(f"Unknown lexical unit ids: {sorted(unknown)}")
    selected = set(unit_ids)
    return tuple(unit.unit_id for unit in dataset.units if unit.unit_id in selected)


def complete_binary_matrix(
    dataset: ValidatedDataset,
    rater_ids: tuple[str, ...],
    unit_ids: tuple[str, ...] | None = None,
) -> BinaryMatrix:
    known_raters = {rater.rater_id for rater in dataset.raters}
    unknown = set(rater_ids) - known_raters
    if unknown:
        raise ValueError(f"Unknown rater ids: {sorted(unknown)}")

    selected_units = _selected_unit_ids(dataset, unit_ids)
    lookup = {
        (annotation.unit_id, annotation.rater_id): _encode(annotation.classification)
        for annotation in dataset.annotations
    }
    values = np.full((len(selected_units), len(rater_ids)), np.nan, dtype=float)
    for row_index, unit_id in enumerate(selected_units):
        for column_index, rater_id in enumerate(rater_ids):
            values[row_index, column_index] = lookup.get((unit_id, rater_id), np.nan)
    return BinaryMatrix(values=values, unit_ids=selected_units, rater_ids=tuple(rater_ids))


def pairwise_vectors(
    dataset: ValidatedDataset,
    rater_a: str,
    rater_b: str,
    unit_ids: tuple[str, ...] | None = None,
) -> PairwiseVectors:
    matrix = complete_binary_matrix(dataset, (rater_a, rater_b), unit_ids)
    mask = matrix.complete_row_mask
    kept_units = tuple(unit_id for unit_id, keep in zip(matrix.unit_ids, mask, strict=True) if keep)
    return PairwiseVectors(
        a=matrix.values[mask, 0].copy(),
        b=matrix.values[mask, 1].copy(),
        unit_ids=kept_units,
    )
