from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.ui.pages.categories import (
    build_category_kappa_figure,
    category_overview_records,
)
from metaphor_agreement_studio.ui.pages.sources import (
    build_source_agreement_figure,
    split_source_groups,
    source_overview_records,
)


def _dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "fire", "Noun", "s1", 1),
        LexicalUnit("u2", "hand", "Noun", "s1", 1),
        LexicalUnit("u3", "fall", "Verb", "s2", 1),
        LexicalUnit("u4", "echo", "Adverb", "s2", 1),
        LexicalUnit("ua1", "fire", "Noun", "agg", 1),
        LexicalUnit("ua2", "hand", "Noun", "agg", 1),
        LexicalUnit("ua3", "fall", "Verb", "agg", 1),
        LexicalUnit("ua4", "echo", "Adverb", "agg", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"))
    values = {
        "r1": [1, 0, 1, 0, 1, 0, 1, 0],
        "r2": [1, 0, 0, 0, 1, 0, 0, 0],
    }
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
        dataset_id="groups-ui",
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


def test_category_rows_keep_n_adjacent_and_singleton_is_descriptive() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    rows = category_overview_records(bundle.by_category, dataset, ("r1", "r2"))

    adverb = next(row for row in rows if row["Category"] == "Adverb")
    assert adverb["N"] == 1
    assert adverb["Cohen's κ"] == "Descriptive result only"
    assert "Pairwise observed agreement" in adverb


def test_category_kappa_plot_keeps_sample_size_in_axis_labels() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    rows = category_overview_records(bundle.by_category, dataset, ("r1", "r2"))

    figure = build_category_kappa_figure(rows)

    assert "Cohen's κ by grammatical category" in figure.layout.title.text
    assert all("n=" in str(label) for label in figure.data[0].y)


def test_source_groups_keep_aggregate_visually_separate() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    primary, aggregate = split_source_groups(bundle.by_source, dataset)

    assert [group.display_name for group in primary] == ["Song A", "Song B"]
    assert [group.display_name for group in aggregate] == ["Combined Videos"]


def test_source_overview_and_plot_include_n_without_double_counting_aggregate() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    primary, _ = split_source_groups(bundle.by_source, dataset)

    rows = source_overview_records(primary, dataset, ("r1", "r2"))
    figure = build_source_agreement_figure(rows)

    assert sum(int(row["N"]) for row in rows) == 4
    assert "Pairwise observed agreement by source" in figure.layout.title.text
    assert all("n=" in str(label) for label in figure.data[0].x)


def _multirater_dataset() -> ValidatedDataset:
    base = _dataset()
    third = Rater("r3", "Sofia")
    values = [1, 1, 0, 0, 1, 1, 0, 0]
    extra = []
    start = len(base.annotations) + 1
    for i, (unit, value) in enumerate(zip(base.units, values, strict=True), start=start):
        classification = Classification.METAPHOR if value else Classification.NON_METAPHOR
        extra.append(
            Annotation(
                annotation_id=f"a{i}",
                unit_id=unit.unit_id,
                rater_id="r3",
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
        dataset_id="groups-ui-3",
        sources=base.sources,
        units=base.units,
        raters=base.raters + (third,),
        annotations=base.annotations + tuple(extra),
        quality_notes=(),
        validation_decisions=(),
    )


def test_multirater_category_rows_and_figure_show_fleiss_kappa() -> None:
    from metaphor_agreement_studio.ui.pages.categories import build_category_fleiss_figure

    dataset = _multirater_dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    rows = category_overview_records(bundle.by_category, dataset, ("r1", "r2"))

    assert all("Fleiss' κ" in row for row in rows)
    assert any(row["_fleiss_value"] is not None for row in rows)
    figure = build_category_fleiss_figure(rows)
    assert "Fleiss' κ by grammatical category" in figure.layout.title.text


def test_multirater_source_rows_and_figure_show_fleiss_kappa() -> None:
    from metaphor_agreement_studio.ui.pages.sources import build_source_fleiss_figure

    dataset = _multirater_dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    primary, _ = split_source_groups(bundle.by_source, dataset)
    rows = source_overview_records(primary, dataset, ("r1", "r2"))

    assert all("Fleiss' κ" in row for row in rows)
    assert any(row["_fleiss_value"] is not None for row in rows)
    figure = build_source_fleiss_figure(rows)
    assert "Fleiss' κ by source" in figure.layout.title.text


def test_category_pairwise_agreement_is_labeled_with_selected_pair() -> None:
    dataset = _multirater_dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    rows = category_overview_records(bundle.by_category, dataset, ("r1", "r2"))
    figure = __import__(
        "metaphor_agreement_studio.ui.pages.categories",
        fromlist=["build_category_agreement_figure"],
    ).build_category_agreement_figure(rows)

    noun = next(row for row in rows if row["Category"] == "Noun")
    assert "Pairwise observed agreement" in noun
    assert noun["Pairwise observed agreement"] == "100.0%"
    assert noun["_pair_label"] == "Eduardo × Braulio"
    assert "Pairwise observed agreement" in figure.layout.title.text
    assert "Eduardo × Braulio" in figure.layout.title.text
    assert "Pairwise observed agreement" in figure.layout.xaxis.title.text


def test_category_rater_counts_respect_selected_sources_and_raters() -> None:
    from metaphor_agreement_studio.ui.filters import AnalysisSelection
    from metaphor_agreement_studio.ui.pages import categories as categories_page

    dataset = _multirater_dataset()
    selection = AnalysisSelection(
        source_ids=("s1",),
        categories=("Noun",),
        rater_ids=("r1", "r3"),
    )

    assert hasattr(categories_page, "rater_counts_for_category")
    frame = categories_page.rater_counts_for_category(dataset, "Noun", selection)

    assert frame["Rater"].tolist() == ["Eduardo", "Sofia"]
    assert frame[["Metaphor", "Non-metaphor", "Missing"]].to_dict("records") == [
        {"Metaphor": 1, "Non-metaphor": 1, "Missing": 0},
        {"Metaphor": 2, "Non-metaphor": 0, "Missing": 0},
    ]


def test_analysis_selection_limits_group_dimensions_and_rater_pairs() -> None:
    from metaphor_agreement_studio.ui.filters import AnalysisSelection

    dataset = _multirater_dataset()
    selection = AnalysisSelection(
        source_ids=("s1",),
        categories=("Noun",),
        rater_ids=("r1", "r3"),
    )
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            selected_source_ids=selection.source_ids,
            selected_categories=selection.categories,
            selected_rater_ids=selection.rater_ids,
            bootstrap_samples=0,
        ),
    )

    assert [group.display_name for group in bundle.by_category] == ["Noun"]
    assert [group.display_name for group in bundle.by_source] == ["Song A"]
    assert {(pair.rater_a_id, pair.rater_b_id) for pair in bundle.pairwise} == {("r1", "r3")}


def test_source_pairwise_agreement_is_labeled_with_selected_pair() -> None:
    dataset = _multirater_dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    primary, _ = split_source_groups(bundle.by_source, dataset)

    rows = source_overview_records(primary, dataset, ("r1", "r2"))
    figure = build_source_agreement_figure(rows)

    assert all("Pairwise observed agreement" in row for row in rows)
    assert all(row["_pair_label"] == "Eduardo × Braulio" for row in rows)
    assert "Pairwise observed agreement" in figure.layout.title.text
    assert "Eduardo × Braulio" in figure.layout.title.text
    assert "Pairwise observed agreement" in figure.layout.yaxis.title.text


def test_pair_can_have_full_agreement_while_multirater_category_contains_disagreement() -> None:
    from metaphor_agreement_studio.review.service import build_review_cases
    from metaphor_agreement_studio.review.types import ReviewStatus

    dataset = _multirater_dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    noun_group = next(group for group in bundle.by_category if group.display_name == "Noun")
    pair = next(
        pair
        for pair in noun_group.pairwise
        if {pair.rater_a_id, pair.rater_b_id} == {"r1", "r2"}
    )
    noun_unit_ids = tuple(
        unit.unit_id for unit in dataset.units
        if not next(source for source in dataset.sources if source.source_id == unit.source_id).is_aggregate
        and unit.grammatical_category == "Noun"
    )
    cases = build_review_cases(dataset, unit_ids=noun_unit_ids)

    assert pair.raw_agreement.value == 1.0
    assert any(case.status is ReviewStatus.DISAGREEMENT for case in cases)
