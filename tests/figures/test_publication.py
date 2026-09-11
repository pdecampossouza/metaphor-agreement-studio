from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd
from PIL import Image

from metaphor_agreement_studio.figures.publication import (
    PUBLICATION_SIZES,
    render_publication_figure,
    save_publication_figure,
)
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureProvenance, FigureSpec


def category_data() -> FigureDataset:
    return FigureDataset(
        FigureKind.AGREEMENT_BY_CATEGORY,
        pd.DataFrame(
            [
                {"category": "Noun", "n": 44, "estimate": 0.62, "ci_low": 0.43, "ci_high": 0.78, "raw_agreement": 0.86, "status": "ok"},
                {"category": "Phrasal verb", "n": 1, "estimate": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "raw_agreement": 1.0, "status": "descriptive_only"},
            ]
        ),
    )


def test_publication_figure_exports_png_svg_pdf_and_png_dpi(tmp_path: Path) -> None:
    fig = render_publication_figure(
        FigureSpec(FigureKind.AGREEMENT_BY_CATEGORY, "Agreement by grammatical category", size_preset="single-column"),
        category_data(),
    )
    assert tuple(round(v, 2) for v in fig.get_size_inches()) == PUBLICATION_SIZES["single-column"]
    for suffix in ("png", "svg", "pdf"):
        out = save_publication_figure(fig, tmp_path / f"figure.{suffix}", suffix, dpi=300)
        assert out.exists() and out.stat().st_size > 0
    with Image.open(tmp_path / "figure.png") as image:
        dpi = image.info.get("dpi")
        assert dpi is not None
        assert abs(dpi[0] - 300) < 2


def test_specific_agreement_uses_distinct_markers_in_monochrome() -> None:
    data = FigureDataset(
        FigureKind.SPECIFIC_AGREEMENT,
        pd.DataFrame(
            [
                {"rater_a": "r1", "rater_b": "r2", "classification": "Metaphor", "estimate": 0.68, "n": 97, "status": "ok"},
                {"rater_a": "r1", "rater_b": "r2", "classification": "Non-metaphor", "estimate": 0.91, "n": 97, "status": "ok"},
            ]
        ),
    )
    fig = render_publication_figure(FigureSpec(FigureKind.SPECIFIC_AGREEMENT, "Specific agreement"), data)
    markers = [line.get_marker() for line in fig.axes[0].lines if line.get_marker() not in (None, "None", "")]
    assert "o" in markers
    assert "x" in markers


def test_save_writes_provenance_sidecar(tmp_path: Path) -> None:
    fig = render_publication_figure(FigureSpec(FigureKind.AGREEMENT_BY_CATEGORY, "Kappa"), category_data())
    provenance = FigureProvenance(
        "Study", "v1.0", "A-001", ("Eduardo", "Braulio"), {}, "0.6.0", "2026-09-05T22:00:00+00:00"
    )
    out = save_publication_figure(fig, tmp_path / "figure_04_kappa_pos.pdf", "pdf", provenance=provenance)
    assert out.exists()
    assert (tmp_path / "figure_04_kappa_pos.provenance.json").exists()
