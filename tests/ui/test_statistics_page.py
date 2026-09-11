from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, EstimateStatus, MetricResult
from metaphor_agreement_studio.ui.pages.statistics import (
    group_statistics_records,
    pairwise_statistics_records,
    status_label,
)


def _dataset() -> ValidatedDataset:
    units = tuple(
        LexicalUnit(f"u{i}", word, pos, "s1", 1)
        for i, (word, pos) in enumerate(
            [("a", "Noun"), ("b", "Noun"), ("c", "Verb"), ("d", "Verb")], start=1
        )
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    values = {"r1": [1, 0, 1, 0], "r2": [1, 0, 0, 0], "r3": [1, 1, 0, 0]}
    annotations = []
    index = 0
    for rater_id, row in values.items():
        for unit, value in zip(units, row, strict=True):
            index += 1
            classification = Classification.METAPHOR if value else Classification.NON_METAPHOR
            annotations.append(
                Annotation(
                    annotation_id=f"a{index}",
                    unit_id=unit.unit_id,
                    rater_id=rater_id,
                    classification=classification,
                    import_id="imp",
                    original_sheet="Sheet1",
                    original_cell=f"A{index}",
                    original_raw_value=classification.value,
                    original_style={},
                    detection_method="fixture",
                    validation_status=ValidationStatus.VALIDATED,
                )
            )
    return ValidatedDataset(
        dataset_id="ui-statistics",
        sources=(Source("s1", "Example"),),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_pairwise_statistics_records_use_rater_names_and_raw_agreement_first() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    records = pairwise_statistics_records(bundle, dataset)

    assert len(records) == 3
    assert records[0]["Rater pair"] == "Eduardo × Braulio"
    assert records[0]["Effective N"] == 4
    assert records[0]["Raw agreement"] == "75.0%"
    assert records[0]["Cohen's κ"] == "0.500"


def test_group_records_include_category_q_and_kappa() -> None:
    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    records = group_statistics_records(bundle.by_category, dataset)

    noun_rows = [row for row in records if row["Group"] == "Noun"]
    assert len(noun_rows) == 3
    assert noun_rows[0]["Lexical units"] == 2
    assert "Cochran's Q" in noun_rows[0]
    assert "Cohen's κ" in noun_rows[0]
    assert "Fleiss' κ" in noun_rows[0]
    assert noun_rows[0]["Fleiss' κ"] != "—"


def test_status_label_explains_no_variation_without_nan() -> None:
    metric = MetricResult(
        metric="cohen_kappa",
        value=None,
        status=EstimateStatus.NOT_ESTIMABLE_NO_VARIATION,
        effective_n=6,
    )

    assert status_label(metric.status) == "Not estimable — no variation"


def test_default_reference_prefers_braulio_for_research_workflow() -> None:
    from metaphor_agreement_studio.ui.pages.statistics import default_reference_rater_id

    dataset = _dataset()

    assert default_reference_rater_id(dataset) == "r2"


def test_expert_benchmark_records_use_explicit_expert_language() -> None:
    from metaphor_agreement_studio.statistics.types import AnalysisPerspective
    from metaphor_agreement_studio.ui.pages.statistics import expert_benchmark_records

    dataset = _dataset()
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.EXPERT_BENCHMARK,
            reference_rater_id="r2",
            bootstrap_samples=0,
        ),
    )

    records = expert_benchmark_records(bundle, dataset)

    assert len(records) == 2
    assert records[0]["Expert benchmark"] == "Braulio"
    assert records[0]["Compared rater"] == "Eduardo"
    assert records[0]["Agreement with expert"] == "75.0%"
    assert records[0]["Sensitivity"] == "100.0%"
    assert records[0]["Specificity"] == "66.7%"
    assert records[0]["Precision"] == "50.0%"
    assert records[0]["Recall"] == "100.0%"
    assert records[0]["Confusion (TP / TN / FP / FN)"] == "1 / 2 / 1 / 0"


def test_default_reference_is_none_when_braulio_is_not_present() -> None:
    from dataclasses import replace

    from metaphor_agreement_studio.domain.models import Rater
    from metaphor_agreement_studio.ui.pages.statistics import default_reference_rater_id

    dataset = replace(
        _dataset(),
        raters=(Rater("r1", "Eduardo"), Rater("r3", "Sofia")),
    )

    assert default_reference_rater_id(dataset) is None


def test_statistical_workspace_exposes_multiple_testing_choices_and_posthoc_records() -> None:
    from metaphor_agreement_studio.ui.pages.statistics import (
        correction_options,
        posthoc_tendency_records,
    )

    dataset = _dataset()
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(bootstrap_samples=0, multiple_testing_correction="holm"),
    )

    assert tuple(correction_options()) == (
        "None",
        "Holm (recommended)",
        "Benjamini-Hochberg",
    )
    rows = posthoc_tendency_records(bundle, dataset)
    assert len(rows) == 3
    assert "Adjusted p-value" in rows[0]
    assert rows[0]["Correction"] == "Holm"


def test_statistical_workspace_links_back_to_validated_annotations() -> None:
    from pathlib import Path

    source = Path("src/metaphor_agreement_studio/ui/pages/statistics.py").read_text(
        encoding="utf-8"
    )

    assert "View validated annotations" in source
    assert "set_route(Route.ANNOTATIONS)" in source
