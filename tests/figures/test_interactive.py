from __future__ import annotations

import pandas as pd

from metaphor_agreement_studio.figures.interactive import render_interactive_figure
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureSpec


def test_multi_rater_patterns_uses_upset_style_bar_and_combination_matrix() -> None:
    data = FigureDataset(
        FigureKind.MULTI_RATER_PATTERNS,
        pd.DataFrame(
            [
                {"pattern": "r1 + r2", "count": 4, "raters": ("r1", "r2")},
                {"pattern": "r2", "count": 2, "raters": ("r2",)},
                {"pattern": "None", "count": 3, "raters": ()},
            ]
        ),
        {"raters": ("r1", "r2", "r3")},
    )
    fig = render_interactive_figure(
        FigureSpec(FigureKind.MULTI_RATER_PATTERNS, "Multi-rater Patterns"),
        data,
    )
    assert fig.layout.yaxis2 is not None
    assert any(trace.type == "bar" for trace in fig.data)
    assert any(trace.type == "scatter" and trace.yaxis == "y2" for trace in fig.data)
