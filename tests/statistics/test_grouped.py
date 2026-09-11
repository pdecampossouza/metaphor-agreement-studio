from __future__ import annotations

from dataclasses import replace

from metaphor_agreement_studio.domain.enums import Classification, SourceType
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.explanations import explanation_text
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def _with_aggregate(dataset: ValidatedDataset) -> ValidatedDataset:
    aggregate = Source("s_agg", "Combined", source_type=SourceType.AGGREGATE, is_aggregate=True)
    cloned_units: list[LexicalUnit] = []
    id_map: dict[str, str] = {}
    for unit in dataset.units:
        cloned_id = f"agg_{unit.unit_id}"
        id_map[unit.unit_id] = cloned_id
        cloned_units.append(
            replace(unit, unit_id=cloned_id, source_id="s_agg")
        )
    cloned_annotations: list[Annotation] = []
    for annotation in dataset.annotations:
        cloned_annotations.append(
            replace(
                annotation,
                annotation_id=f"agg_{annotation.annotation_id}",
                unit_id=id_map[annotation.unit_id],
            )
        )
    return replace(
        dataset,
        dataset_id="with_aggregate",
        sources=dataset.sources + (aggregate,),
        units=dataset.units + tuple(cloned_units),
        annotations=dataset.annotations + tuple(cloned_annotations),
    )


def test_grouped_analysis_has_categories_sources_and_all_rater_pairs(binary_dataset) -> None:
    bundle = analyze_dataset(binary_dataset, AnalysisConfig(bootstrap_samples=200))

    assert [group.group_id for group in bundle.by_category] == ["Noun", "Verb"]
    assert [group.lexical_unit_count for group in bundle.by_category] == [2, 2]
    assert all(len(group.pairwise) == 3 for group in bundle.by_category)
    assert [group.group_id for group in bundle.by_source] == ["s1"]
    assert len(bundle.pairwise) == 3
    assert len(bundle.specific_agreement) == 3
    assert len(bundle.overall_multirater) == 2
    assert bundle.cochran_q is not None


def test_default_overall_excludes_aggregate_units_without_hiding_source_analysis(binary_dataset) -> None:
    dataset = _with_aggregate(binary_dataset)

    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=200))

    assert bundle.counts.lexical_units == 4
    assert bundle.counts.total_ratings == 12
    assert {group.group_id for group in bundle.by_source} == {"s1", "s_agg"}


def test_aggregate_can_be_selected_explicitly_as_analysis_source(binary_dataset) -> None:
    dataset = _with_aggregate(binary_dataset)
    config = AnalysisConfig(selected_source_ids=("s_agg",), bootstrap_samples=200)

    bundle = analyze_dataset(dataset, config)

    assert bundle.counts.lexical_units == 4
    assert [group.group_id for group in bundle.by_source] == ["s_agg"]


def test_prevalence_warning_is_stable_key_with_plain_english_explanation(binary_dataset) -> None:
    annotations = []
    for index, annotation in enumerate(binary_dataset.annotations):
        classification = Classification.METAPHOR if index == 0 else Classification.NON_METAPHOR
        annotations.append(replace(annotation, classification=classification))
    dataset = replace(binary_dataset, dataset_id="imbalanced", annotations=tuple(annotations))

    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=200))

    assert "class_imbalance_kappa_prevalence" in bundle.warnings
    text = explanation_text("class_imbalance_kappa_prevalence").lower()
    assert "sensitive to prevalence" in text
    assert "raw" in text
    assert "class-specific" in text


def test_multirater_group_results_include_fleiss_kappa_by_category_and_source(binary_dataset) -> None:
    bundle = analyze_dataset(binary_dataset, AnalysisConfig(bootstrap_samples=0))

    assert all(group.fleiss_kappa is not None for group in bundle.by_category)
    assert all(group.fleiss_kappa.metric == "fleiss_kappa" for group in bundle.by_category)
    assert all(group.fleiss_kappa is not None for group in bundle.by_source)
    assert all(group.fleiss_kappa.metric == "fleiss_kappa" for group in bundle.by_source)
