from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.review.service import build_review_cases
from metaphor_agreement_studio.review.types import ReviewStatus
from metaphor_agreement_studio.ui.pages.review import (
    REVIEW_HELP_TEXT,
    build_annotation_map_figure,
    filter_review_cases,
    review_summary,
)


def _dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "fire", "Noun", "s1", 1),
        LexicalUnit("u2", "hand", "Noun", "s1", 1),
        LexicalUnit("u3", "fall", "Verb", "s1", 1, context="we fall into silence"),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    rows = {
        "r1": [1, 0, 1],
        "r2": [1, 0, 1],
        "r3": [1, 0, 0],
    }
    annotations = []
    i = 0
    for rater_id, values in rows.items():
        for unit, value in zip(units, values, strict=True):
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
        dataset_id="review-ui",
        sources=(Source("s1", "Song A"),),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_review_summary_counts_cases_that_require_review_without_quality_language() -> None:
    cases = build_review_cases(_dataset())

    summary = review_summary(cases)

    assert summary["requires_review"] == 1
    assert summary["unanimous"] == 2
    assert "wrong rater" not in REVIEW_HELP_TEXT.lower()
    assert "incorrect rater" not in REVIEW_HELP_TEXT.lower()
    assert "bad agreement" not in REVIEW_HELP_TEXT.lower()


def test_unanimous_cases_are_valid_states_not_errors() -> None:
    cases = build_review_cases(_dataset())
    fire = next(case for case in cases if case.unit_id == "u1")

    assert fire.status is ReviewStatus.UNANIMOUS_METAPHOR
    assert fire.agreement_fraction == 1.0


def test_focus_rater_filter_surfaces_only_cases_where_selected_rater_diverges() -> None:
    cases = build_review_cases(_dataset())

    filtered = filter_review_cases(cases, focus_rater_id="r3", mode="Focus rater differs")

    assert [case.unit_id for case in filtered] == ["u3"]


def test_annotation_map_is_visual_and_keeps_symbolic_classification_encoding() -> None:
    dataset = _dataset()
    cases = build_review_cases(dataset)

    figure = build_annotation_map_figure(cases, dataset)

    assert "Annotation agreement map" in figure.layout.title.text
    trace_names = {trace.name for trace in figure.data}
    assert "Metaphor" in trace_names
    assert "Non-metaphor" in trace_names
    symbols = {trace.marker.symbol for trace in figure.data}
    assert len(symbols) >= 2


def test_review_default_sources_exclude_aggregate_views() -> None:
    from dataclasses import replace

    from metaphor_agreement_studio.ui.pages.review import default_review_source_ids

    dataset = _dataset()
    dataset = replace(
        dataset,
        sources=dataset.sources + (Source("agg", "Combined", is_aggregate=True),),
    )

    assert default_review_source_ids(dataset) == ("s1",)


def test_review_selected_unit_ids_respect_shared_analysis_selection() -> None:
    from metaphor_agreement_studio.ui.filters import AnalysisSelection
    from metaphor_agreement_studio.ui.pages import review as review_page

    dataset = _dataset()
    selection = AnalysisSelection(
        source_ids=("s1",),
        categories=("Verb",),
        rater_ids=("r1", "r3"),
    )

    assert hasattr(review_page, "selected_review_unit_ids")
    assert review_page.selected_review_unit_ids(dataset, selection) == ("u3",)


def test_review_status_recalculates_for_selected_rater_subset() -> None:
    from metaphor_agreement_studio.ui.filters import AnalysisSelection
    from metaphor_agreement_studio.ui.pages import review as review_page

    dataset = _dataset()
    assert hasattr(review_page, "selected_review_unit_ids")

    divergent_selection = AnalysisSelection(
        source_ids=("s1",),
        categories=("Verb",),
        rater_ids=("r1", "r3"),
    )
    unit_ids = review_page.selected_review_unit_ids(dataset, divergent_selection)
    divergent = build_review_cases(
        dataset,
        selected_raters=divergent_selection.rater_ids,
        unit_ids=unit_ids,
    )

    unanimous_selection = AnalysisSelection(
        source_ids=("s1",),
        categories=("Verb",),
        rater_ids=("r1", "r2"),
    )
    unanimous = build_review_cases(
        dataset,
        selected_raters=unanimous_selection.rater_ids,
        unit_ids=review_page.selected_review_unit_ids(dataset, unanimous_selection),
    )

    assert divergent[0].status is ReviewStatus.DISAGREEMENT
    assert unanimous[0].status is ReviewStatus.UNANIMOUS_METAPHOR
