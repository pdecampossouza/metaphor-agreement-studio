from __future__ import annotations

from metaphor_agreement_studio.reporting.latex import escape_latex, render_figure_latex, render_latex_table
from metaphor_agreement_studio.statistics.types import (
    AnalysisBundle,
    AnalysisConfig,
    CountSummary,
    EstimateStatus,
    GroupResult,
    MetricResult,
    PairwiseResult,
)


def pair() -> PairwiseResult:
    return PairwiseResult(
        "r1",
        "r2",
        MetricResult("raw_agreement", 0.8, EstimateStatus.OK, 10),
        MetricResult("cohen_kappa", 0.5, EstimateStatus.OK, 10, ci_low=0.2, ci_high=0.7),
        ((4, 1), (1, 4)),
    )


def bundle() -> AnalysisBundle:
    group = GroupResult("A&B_#1", "Noun {special} 50% & more_", 10, (pair(),), None)
    return AnalysisBundle(
        AnalysisConfig(selected_rater_ids=("r1", "r2")),
        CountSummary(10, 2, 20, 8, 12, 0, (("Noun {special} 50% & more_", 10),)),
        (pair(),),
        (),
        None,
        (),
        (),
        (),
        (group,),
        (group,),
        (),
    )


def test_escape_latex_handles_user_text_special_characters() -> None:
    escaped = escape_latex(r"A&B_#1 {x} 50%")
    for token in (r"\&", r"\_", r"\#", r"\{", r"\}", r"\%"):
        assert token in escaped


def test_latex_table_escapes_group_labels() -> None:
    text = render_latex_table("by_category", bundle(), selection={"rater_pair": ("r1", "r2")})
    assert r"Noun \{special\} 50\% \& more\_" in text
    assert "0.50" in text
    assert "10" in text


def test_figure_latex_escapes_caption_and_label() -> None:
    text = render_figure_latex("figure_01.pdf", "A&B 50%", "fig:kappa_pos")
    assert r"A\&B 50\%" in text
    assert r"\label{fig:kappa-pos}" in text
