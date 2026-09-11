from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, EstimateStatus, MetricResult
from metaphor_agreement_studio.ui.filters import default_analysis_selection
from metaphor_agreement_studio.ui.legends import ANNOTATION_LEGEND_ITEMS
from metaphor_agreement_studio.ui.metric_components import metric_display_model
from metaphor_agreement_studio.ui.pages.agreement import (
    AGREEMENT_SECTION_TITLES,
    COCHRAN_Q_HELP,
    build_pairwise_kappa_figure,
    build_pairwise_kappa_matrix,
    build_rater_tendency_figure,
    rater_tendency_records,
)


def _dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "fire", "Noun", "s1", 1),
        LexicalUnit("u2", "hand", "Noun", "s1", 1),
        LexicalUnit("u3", "fall", "Verb", "s2", 1),
        LexicalUnit("u4", "echo", "Verb", "s2", 1),
        LexicalUnit("ua", "combined", "Verb", "agg", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    rows = {
        "r1": [1, 0, 1, 0, 1],
        "r2": [1, 0, 0, 0, 1],
        "r3": [1, 1, 0, 0, 1],
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
        dataset_id="agreement-ui",
        sources=(
            Source("s1", "Song A"),
            Source("s2", "Song B"),
            Source("agg", "Combined Videos", is_aggregate=True),
        ),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_default_filters_exclude_aggregate_but_include_all_categories_and_raters() -> None:
    dataset = _dataset()
    selection = default_analysis_selection(dataset)

    assert selection.source_ids == ("s1", "s2")
    assert selection.categories == ("Noun", "Verb")
    assert selection.rater_ids == ("r1", "r2", "r3")


def test_annotation_legend_is_understandable_without_color() -> None:
    labels = [item.label for item in ANNOTATION_LEGEND_ITEMS]

    assert labels == ["Metaphor", "Non-metaphor", "Missing / not rated", "Requires review"]
    assert all(item.symbol for item in ANNOTATION_LEGEND_ITEMS)


def test_non_estimable_metric_has_explanation_not_nan() -> None:
    result = MetricResult(
        metric="cohen_kappa",
        value=None,
        status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
        effective_n=7,
    )

    model = metric_display_model("Cohen's κ", result)

    assert model.value == "Not estimable"
    assert "no variation" in model.explanation.lower()
    assert "nan" not in (model.value + model.explanation).lower()


def test_agreement_page_separates_agreement_from_tendency() -> None:
    assert AGREEMENT_SECTION_TITLES[:3] == (
        "Observed agreement",
        "Pairwise agreement",
        "Overall multi-rater agreement",
    )
    assert "Rater classification tendency" in AGREEMENT_SECTION_TITLES
    assert "tests whether raters differ" in COCHRAN_Q_HELP
    assert "agreement coefficient" in COCHRAN_Q_HELP


def test_pairwise_kappa_matrix_is_symmetric_and_uses_names() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    matrix = build_pairwise_kappa_matrix(bundle, dataset)

    assert matrix.index.tolist() == ["Eduardo", "Braulio", "Sofia"]
    assert matrix.columns.tolist() == ["Eduardo", "Braulio", "Sofia"]
    assert matrix.loc["Eduardo", "Braulio"] == matrix.loc["Braulio", "Eduardo"]
    assert matrix.loc["Eduardo", "Eduardo"] == 1.0


def test_agreement_figures_are_real_plotly_charts_with_scientific_titles() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    kappa_fig = build_pairwise_kappa_figure(bundle, dataset)
    tendency_fig = build_rater_tendency_figure(rater_tendency_records(dataset, default_analysis_selection(dataset)))

    assert "Pairwise Cohen" in kappa_fig.layout.title.text
    assert kappa_fig.data[0].type == "heatmap"
    assert "Metaphor classification rate" in tendency_fig.layout.title.text
    assert tendency_fig.data[0].type == "bar"
