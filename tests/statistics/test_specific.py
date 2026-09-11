from __future__ import annotations

import numpy as np
import pytest

from metaphor_agreement_studio.statistics.specific import specific_agreement


def test_specific_agreement_matches_symmetric_binary_definition() -> None:
    result = specific_agreement(
        np.array([1, 0, 1, 0], dtype=float),
        np.array([1, 0, 0, 0], dtype=float),
    )

    assert result.metaphor_agreement.value == pytest.approx(2 / 3)
    assert result.non_metaphor_agreement.value == pytest.approx(4 / 5)
    assert result.metaphor_agreement.effective_n == 4
    assert result.non_metaphor_agreement.effective_n == 4
