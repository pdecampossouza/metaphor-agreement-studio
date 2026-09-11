from __future__ import annotations

import numpy as np
import pytest

from metaphor_agreement_studio.statistics.pairwise import cohen_kappa
from metaphor_agreement_studio.statistics.types import EstimateStatus


def test_cohen_kappa_matches_independently_known_value() -> None:
    result = cohen_kappa(
        np.array([1, 1, 0, 0], dtype=float),
        np.array([1, 0, 0, 0], dtype=float),
        bootstrap_samples=500,
        seed=42,
    )

    assert result.raw_agreement.value == pytest.approx(0.75)
    assert result.kappa.value == pytest.approx(0.5)
    assert result.kappa.effective_n == 4
    assert result.contingency == ((2, 0), (1, 1))


def test_perfect_agreement_without_variation_is_explained_not_nan() -> None:
    result = cohen_kappa(np.array([0, 0, 0]), np.array([0, 0, 0]))

    assert result.raw_agreement.value == 1.0
    assert result.kappa.value is None
    assert result.kappa.status == EstimateStatus.NOT_ESTIMABLE_NO_VARIATION
    assert "perfect_agreement_no_variation" in result.kappa.explanation_keys


def test_one_complete_pair_is_descriptive_only() -> None:
    result = cohen_kappa(np.array([1.0]), np.array([1.0]))

    assert result.raw_agreement.value == 1.0
    assert result.kappa.value is None
    assert result.kappa.status == EstimateStatus.DESCRIPTIVE_ONLY
    assert "one_item_descriptive_only" in result.kappa.explanation_keys


def test_no_complete_pair_is_insufficient() -> None:
    result = cohen_kappa(np.array([np.nan]), np.array([1.0]))

    assert result.raw_agreement.value is None
    assert result.kappa.value is None
    assert result.kappa.status == EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS
    assert result.kappa.effective_n == 0


def test_bootstrap_confidence_interval_is_deterministic_when_estimable() -> None:
    a = np.array([1, 1, 1, 0, 0, 0, 1, 0], dtype=float)
    b = np.array([1, 1, 0, 0, 0, 1, 1, 0], dtype=float)

    first = cohen_kappa(a, b, bootstrap_samples=500, seed=20260905)
    second = cohen_kappa(a, b, bootstrap_samples=500, seed=20260905)

    assert first.kappa.ci_low == second.kappa.ci_low
    assert first.kappa.ci_high == second.kappa.ci_high
    assert first.kappa.ci_low is not None
    assert first.kappa.ci_high is not None
    assert first.kappa.ci_low <= first.kappa.value <= first.kappa.ci_high
