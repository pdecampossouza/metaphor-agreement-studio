from __future__ import annotations

from metaphor_agreement_studio.figures.interactive import render_interactive_figure
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureSpec
from metaphor_agreement_studio.ui.pages.figures import FIGURE_GALLERY

import pandas as pd


def test_figure_gallery_exposes_all_approved_core_figures() -> None:
    labels = {item.label for item in FIGURE_GALLERY}
    assert labels == {
        "Annotation Agreement Map",
        "Pairwise Kappa Matrix",
        "Agreement by Grammatical Category",
        "Agreement vs Sample Size",
        "Metaphor Classification Rates",
        "Disagreement by Grammatical Category",
        "Rater Divergence Profile",
        "Multi-rater Patterns",
        "Source Comparison",
        "Specific Agreement",
        "Disagreement Density Map",
    }


def test_pairwise_kappa_interactive_hover_contains_audit_fields() -> None:
    data = FigureDataset(
        FigureKind.PAIRWISE_KAPPA_MATRIX,
        pd.DataFrame(
            [
                {
                    "rater_a": "r1",
                    "rater_b": "r2",
                    "estimate": 0.48,
                    "raw_agreement": 0.72,
                    "n": 97,
                    "ci_low": 0.30,
                    "ci_high": 0.64,
                    "status": "ok",
                },
                {
                    "rater_a": "r1",
                    "rater_b": "r1",
                    "estimate": float("nan"),
                    "raw_agreement": float("nan"),
                    "n": float("nan"),
                    "ci_low": float("nan"),
                    "ci_high": float("nan"),
                    "status": "diagonal",
                },
            ]
        ),
    )
    fig = render_interactive_figure(FigureSpec(FigureKind.PAIRWISE_KAPPA_MATRIX, "Pairwise"), data)
    assert fig.layout.title.text == "Pairwise"
    hover = " ".join(str(trace.hovertemplate) for trace in fig.data)
    assert "Cohen" in hover
    assert "Raw agreement" in hover
    assert "Effective N" in hover
    assert "95% CI" in hover

from metaphor_agreement_studio.ui.pages.export_center import EXPORT_GROUPS


def test_export_center_uses_approved_research_groups() -> None:
    assert tuple(EXPORT_GROUPS) == ("DATA", "STATISTICAL RESULTS", "PUBLICATION", "DOCUMENTATION")
    assert "Validated annotations" in EXPORT_GROUPS["DATA"]
    assert "Publication figures" in EXPORT_GROUPS["PUBLICATION"]
    assert "Reproducibility manifest" in EXPORT_GROUPS["DOCUMENTATION"]

from metaphor_agreement_studio.ui.pages.figures import PUBLICATION_EXPORT_FORMATS, PUBLICATION_SIZE_OPTIONS


def test_figures_page_exposes_publication_export_controls() -> None:
    assert PUBLICATION_EXPORT_FORMATS == ("PDF", "SVG", "PNG")
    assert PUBLICATION_SIZE_OPTIONS == ("single-column", "double-column", "presentation")


def test_export_center_maps_each_checkbox_to_its_own_artifact_flag() -> None:
    from metaphor_agreement_studio.ui.pages.export_center import _package_artifact_flags

    selections = {item: False for items in EXPORT_GROUPS.values() for item in items}
    selections["Validated annotations"] = True
    flags = _package_artifact_flags(selections)
    assert flags["include_validated_xlsx"] is True
    assert flags["include_long_csv"] is False
    assert flags["include_results_workbook"] is False
    assert flags["include_publication_figures"] is False
    assert flags["include_latex_tables"] is False
    assert flags["include_reporting_text"] is False
    assert flags["include_validation_summary"] is False
    assert flags["include_analysis_settings"] is False
