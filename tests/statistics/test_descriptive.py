from __future__ import annotations

import numpy as np
import pytest

from metaphor_agreement_studio.statistics.descriptive import dataset_counts, raw_pairwise_agreement


def test_dataset_counts_exact_binary_fixture(binary_dataset) -> None:
    counts = dataset_counts(binary_dataset)

    assert counts.lexical_units == 4
    assert counts.raters == 3
    assert counts.total_ratings == 12
    assert counts.metaphor_ratings == 5
    assert counts.non_metaphor_ratings == 7
    assert counts.missing_ratings == 0
    assert dict(counts.category_counts) == {"Noun": 2, "Verb": 2}


def test_dataset_counts_treat_absent_or_explicit_ratings_as_missing(dataset_with_missing) -> None:
    counts = dataset_counts(dataset_with_missing)

    assert counts.total_ratings == 12
    assert counts.metaphor_ratings == 5
    assert counts.non_metaphor_ratings == 5
    assert counts.missing_ratings == 2


def test_dataset_counts_are_based_on_selected_units_not_annotation_rows(binary_dataset) -> None:
    counts = dataset_counts(binary_dataset, ("u1", "u3"))

    assert counts.lexical_units == 2
    assert counts.total_ratings == 6
    assert dict(counts.category_counts) == {"Noun": 1, "Verb": 1}


def test_raw_pairwise_agreement_is_three_quarters() -> None:
    result = raw_pairwise_agreement(np.array([1, 0, 1, 0]), np.array([1, 0, 0, 0]))

    assert result.value == pytest.approx(0.75)
    assert result.effective_n == 4
