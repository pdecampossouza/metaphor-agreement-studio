from __future__ import annotations

import numpy as np
import pytest
from statsmodels.stats.inter_rater import fleiss_kappa as sm_fleiss_kappa

from metaphor_agreement_studio.statistics.multirater import fleiss_kappa, krippendorff_alpha
from metaphor_agreement_studio.statistics.types import EstimateStatus


def test_fleiss_kappa_matches_statsmodels_reference(binary_dataset) -> None:
    category_counts = np.array(
        [
            [0, 3],
            [2, 1],
            [2, 1],
            [3, 0],
        ],
        dtype=float,
    )
    expected = float(sm_fleiss_kappa(category_counts))

    result = fleiss_kappa(binary_dataset, ("r1", "r2", "r3"))

    assert result.value == pytest.approx(expected)
    assert result.effective_n == 4
    assert result.status == EstimateStatus.OK


def test_fleiss_uses_complete_units_and_reports_reduced_effective_n(dataset_with_missing) -> None:
    result = fleiss_kappa(dataset_with_missing, ("r1", "r2", "r3"))

    assert result.effective_n == 2
    assert result.value is not None
    assert "fleiss_complete_cases_only" in result.explanation_keys


def test_krippendorff_alpha_uses_available_nominal_ratings_with_missing(dataset_with_missing) -> None:
    result = krippendorff_alpha(dataset_with_missing, ("r1", "r2", "r3"))

    assert result.effective_n == 4
    assert result.value is not None
    assert np.isfinite(result.value)
    assert result.status == EstimateStatus.OK


def test_krippendorff_alpha_matches_independent_coincidence_reference(binary_dataset) -> None:
    # For the fixture, the coincidence matrix is [[5,2],[2,3]].
    # Do = 4/12 and De = 6.363636.../12, giving alpha = 13/35.
    result = krippendorff_alpha(binary_dataset, ("r1", "r2", "r3"))

    assert result.value == pytest.approx(13 / 35)


def test_multirater_no_variation_returns_explicit_state(no_variation_dataset) -> None:
    fleiss = fleiss_kappa(no_variation_dataset, ("r1", "r2", "r3"))
    alpha = krippendorff_alpha(no_variation_dataset, ("r1", "r2", "r3"))

    assert fleiss.value is None
    assert alpha.value is None
    assert fleiss.status == EstimateStatus.NOT_ESTIMABLE_NO_VARIATION
    assert alpha.status == EstimateStatus.NOT_ESTIMABLE_NO_VARIATION


def test_krippendorff_alpha_is_independent_of_external_runtime_package(monkeypatch, binary_dataset) -> None:
    import sys
    import types

    fake = types.ModuleType("krippendorff")
    fake.alpha = lambda **kwargs: -999.0
    monkeypatch.setitem(sys.modules, "krippendorff", fake)

    result = krippendorff_alpha(binary_dataset, ("r1", "r2", "r3"))

    assert result.value == pytest.approx(13 / 35)
    assert "krippendorff_internal_nominal_fallback" in result.explanation_keys
