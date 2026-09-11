from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from metaphor_agreement_studio.domain.imports import ValidatedDataset


@dataclass(frozen=True, slots=True)
class AnalysisSelection:
    source_ids: tuple[str, ...]
    categories: tuple[str, ...]
    rater_ids: tuple[str, ...]


def default_analysis_selection(dataset: ValidatedDataset) -> AnalysisSelection:
    source_ids = tuple(source.source_id for source in dataset.sources if not source.is_aggregate)
    source_set = set(source_ids)
    categories = tuple(
        sorted(
            {
                unit.grammatical_category
                for unit in dataset.units
                if unit.source_id in source_set
            }
        )
    )
    rater_ids = tuple(rater.rater_id for rater in dataset.raters)
    return AnalysisSelection(source_ids=source_ids, categories=categories, rater_ids=rater_ids)


def _normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    ).casefold()


def default_reference_rater_id(dataset: ValidatedDataset) -> str | None:
    for rater in dataset.raters:
        if _normalized_name(rater.display_name) == "braulio":
            return rater.rater_id
    return None


def render_analysis_filters(dataset: ValidatedDataset, key_prefix: str) -> AnalysisSelection:
    import streamlit as st

    defaults = default_analysis_selection(dataset)
    source_names = {source.source_id: source.display_name for source in dataset.sources}
    rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    source_options = tuple(source_names)
    category_options = tuple(sorted({unit.grammatical_category for unit in dataset.units}))
    rater_options = tuple(rater_names)

    columns = st.columns((1.25, 1.15, 1.25))
    source_ids = tuple(
        columns[0].multiselect(
            "Sources",
            source_options,
            default=defaults.source_ids,
            format_func=lambda source_id: source_names[source_id],
            key=f"{key_prefix}_sources",
        )
    )
    categories = tuple(
        columns[1].multiselect(
            "Grammatical categories",
            category_options,
            default=defaults.categories,
            key=f"{key_prefix}_categories",
        )
    )
    rater_ids = tuple(
        columns[2].multiselect(
            "Raters",
            rater_options,
            default=defaults.rater_ids,
            format_func=lambda rater_id: rater_names[rater_id],
            key=f"{key_prefix}_raters",
        )
    )

    aggregate_ids = {source.source_id for source in dataset.sources if source.is_aggregate}
    if aggregate_ids.intersection(source_ids) and any(
        source_id not in aggregate_ids for source_id in source_ids
    ):
        st.warning(
            "An aggregate source is selected together with primary sources. The same lexical material may "
            "therefore appear more than once in this filtered view.",
            icon=":material/warning:",
        )
    return AnalysisSelection(source_ids=source_ids, categories=categories, rater_ids=rater_ids)
