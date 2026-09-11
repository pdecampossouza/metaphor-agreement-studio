from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, AnalysisPerspective
from metaphor_agreement_studio.ui.pages.rater_explorer import (
    DIVERGENCE_EXPLANATION,
    build_focus_kappa_figure,
    focus_pairwise_records,
    suggested_focus_rater_id,
)


def _dataset() -> ValidatedDataset:
    units = tuple(
        LexicalUnit(f"u{i}", word, "Noun", "s1", 1)
        for i, word in enumerate(("fire", "hand", "fall", "echo"), 1)
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    values = {"r1": [1, 0, 1, 0], "r2": [1, 0, 0, 0], "r3": [1, 1, 0, 0]}
    annotations = []
    i = 0
    for rater_id, row in values.items():
        for unit, value in zip(units, row, strict=True):
            i += 1
            classification = Classification.METAPHOR if value else Classification.NON_METAPHOR
            annotations.append(
                Annotation(
                    annotation_id=f"a{i}",
                    unit_id=unit.unit_id,
                    rater_id=rater_id,
                    classification=classification,
                    import_id="imp",
                    original_sheet="Sheet1",
                    original_cell=f"A{i}",
                    original_raw_value=classification.value,
                    original_style={},
                    detection_method="fixture",
                    validation_status=ValidationStatus.VALIDATED,
                )
            )
    return ValidatedDataset(
        dataset_id="rater-ui",
        sources=(Source("s1", "Song A"),),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_suggested_focus_prefers_braulio_but_is_not_hard_coded_as_only_choice() -> None:
    dataset = _dataset()

    assert suggested_focus_rater_id(dataset) == "r2"
    assert tuple(rater.rater_id for rater in dataset.raters) == ("r1", "r2", "r3")


def test_focus_records_show_each_comparison_against_selected_rater() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
            reference_rater_id="r2",
            bootstrap_samples=0,
        ),
    )

    rows = focus_pairwise_records(bundle, dataset, "r2")

    assert [row["Compared with"] for row in rows] == ["Eduardo", "Sofia"]
    assert all("Cohen's κ" in row for row in rows)
    assert all("Observed agreement" in row for row in rows)


def test_focus_chart_is_visual_and_divergence_copy_does_not_imply_error() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
            reference_rater_id="r2",
            bootstrap_samples=0,
        ),
    )
    rows = focus_pairwise_records(bundle, dataset, "r2")

    figure = build_focus_kappa_figure(rows, "Braulio")

    assert figure.data[0].type == "bar"
    assert "Braulio" in figure.layout.title.text
    assert DIVERGENCE_EXPLANATION == (
        "Lower agreement indicates greater divergence from the other raters; "
        "it does not indicate that a rater is incorrect."
    )


def test_rater_explorer_offers_traceable_annotation_drilldown() -> None:
    from pathlib import Path

    source = Path("src/metaphor_agreement_studio/ui/pages/rater_explorer.py").read_text(
        encoding="utf-8"
    )

    assert "Open focus rater in Annotations" in source
    assert 'st.session_state["annotations_rater_filter"]' in source
