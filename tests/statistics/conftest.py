from __future__ import annotations

from dataclasses import replace

import pytest

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source


def annotation(unit_id: str, rater_id: str, value: Classification, i: int) -> Annotation:
    return Annotation(
        annotation_id=f"a{i}",
        unit_id=unit_id,
        rater_id=rater_id,
        classification=value,
        import_id="imp",
        original_sheet="Sheet1",
        original_cell=f"A{i}",
        original_raw_value=value.value,
        original_style={},
        detection_method="fixture",
        validation_status=ValidationStatus.VALIDATED,
    )


def _base_dataset(values: dict[str, list[int | None]], dataset_id: str) -> ValidatedDataset:
    units = tuple(
        LexicalUnit(f"u{i}", word, pos, "s1", 1)
        for i, (word, pos) in enumerate(
            [("a", "Noun"), ("b", "Noun"), ("c", "Verb"), ("d", "Verb")],
            start=1,
        )
    )
    raters = (
        Rater("r1", "Eduardo"),
        Rater("r2", "Braulio"),
        Rater("r3", "Sofia"),
    )
    anns: list[Annotation] = []
    j = 0
    for rater_id, row in values.items():
        for unit, value in zip(units, row, strict=True):
            j += 1
            if value is None:
                classification = Classification.MISSING
            else:
                classification = (
                    Classification.METAPHOR if value else Classification.NON_METAPHOR
                )
            anns.append(annotation(unit.unit_id, rater_id, classification, j))
    return ValidatedDataset(
        dataset_id=dataset_id,
        sources=(Source("s1", "Example"),),
        units=units,
        raters=raters,
        annotations=tuple(anns),
        quality_notes=(),
        validation_decisions=(),
    )


@pytest.fixture
def binary_dataset() -> ValidatedDataset:
    return _base_dataset(
        {
            "r1": [1, 0, 1, 0],
            "r2": [1, 0, 0, 0],
            "r3": [1, 1, 0, 0],
        },
        "d1",
    )


@pytest.fixture
def dataset_with_missing() -> ValidatedDataset:
    return _base_dataset(
        {
            "r1": [1, 0, 1, 0],
            "r2": [1, 0, None, 0],
            "r3": [1, 1, 0, None],
        },
        "d_missing",
    )


@pytest.fixture
def no_variation_dataset(binary_dataset: ValidatedDataset) -> ValidatedDataset:
    anns = tuple(
        replace(annotation, classification=Classification.NON_METAPHOR)
        for annotation in binary_dataset.annotations
    )
    return replace(binary_dataset, dataset_id="d_constant", annotations=anns)
