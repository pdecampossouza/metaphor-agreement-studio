from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import chi2
from statsmodels.stats.multitest import multipletests

from metaphor_agreement_studio.statistics.tendency import cochran_q, posthoc_mcnemar
from metaphor_agreement_studio.statistics.types import EstimateStatus


def test_cochran_q_matches_closed_form_reference() -> None:
    x = np.array([[1, 1, 0], [1, 0, 0], [1, 1, 1], [0, 0, 1]], dtype=float)
    k = x.shape[1]
    col = x.sum(axis=0)
    row = x.sum(axis=1)
    q_expected = (k - 1) * (k * (col**2).sum() - col.sum() ** 2) / (
        k * row.sum() - (row**2).sum()
    )

    result = cochran_q(x)

    assert result.q == pytest.approx(q_expected)
    assert result.degrees_of_freedom == 2
    assert result.p_value == pytest.approx(chi2.sf(q_expected, 2))
    assert result.effective_n == 4
    assert result.status == EstimateStatus.OK


def test_cochran_q_unanimous_constant_matrix_is_non_estimable() -> None:
    result = cochran_q(np.zeros((5, 3), dtype=float))

    assert result.q is None
    assert result.p_value is None
    assert result.status == EstimateStatus.NOT_ESTIMABLE_NO_VARIATION
    assert result.effective_n == 5


def test_two_rater_cochran_q_keeps_requested_test_and_adds_mcnemar_note() -> None:
    x = np.array([[1, 0], [1, 1], [0, 0], [0, 1]], dtype=float)

    result = cochran_q(x)

    assert result.degrees_of_freedom == 1
    assert "two_rater_q_related_to_mcnemar" in result.explanation_keys


def test_cochran_q_drops_incomplete_rows_only() -> None:
    x = np.array([[1, 1, 0], [1, np.nan, 0], [0, 0, 1]], dtype=float)

    result = cochran_q(x)

    assert result.effective_n == 2


def test_posthoc_holm_adjustment_matches_statsmodels() -> None:
    matrix = np.array(
        [
            [1, 0, 0],
            [1, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 0, 1],
            [0, 0, 0],
        ],
        dtype=float,
    )
    raw = posthoc_mcnemar(matrix, ("r1", "r2", "r3"), correction="none")
    holm = posthoc_mcnemar(matrix, ("r1", "r2", "r3"), correction="holm")
    raw_p = np.array([item.p_value for item in raw], dtype=float)
    expected = multipletests(raw_p, method="holm")[1]

    assert [item.adjusted_p_value for item in holm] == pytest.approx(expected.tolist())


def test_posthoc_bh_uses_fdr_bh_mapping() -> None:
    matrix = np.array(
        [[1, 0, 0], [1, 0, 1], [0, 0, 1], [0, 1, 1], [1, 1, 0]], dtype=float
    )
    raw = posthoc_mcnemar(matrix, ("r1", "r2", "r3"), correction="none")
    bh = posthoc_mcnemar(matrix, ("r1", "r2", "r3"), correction="benjamini-hochberg")
    raw_p = np.array([item.p_value for item in raw], dtype=float)
    expected = multipletests(raw_p, method="fdr_bh")[1]

    assert [item.adjusted_p_value for item in bh] == pytest.approx(expected.tolist())
