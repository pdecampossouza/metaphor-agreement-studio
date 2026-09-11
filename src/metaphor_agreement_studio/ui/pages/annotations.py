from __future__ import annotations

from collections import defaultdict

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.ui.components import page_header, semantic_legend


def _classification_label(value: Classification) -> str:
    if value == Classification.METAPHOR:
        return "Metaphor"
    if value == Classification.NON_METAPHOR:
        return "Non-metaphor"
    return "Missing"


def annotation_records(dataset: ValidatedDataset) -> list[dict[str, object]]:
    source_by_id = {source.source_id: source for source in dataset.sources}
    rater_by_id = {rater.rater_id: rater for rater in dataset.raters}
    annotations_by_unit: dict[str, dict[str, Classification]] = defaultdict(dict)
    for annotation in dataset.annotations:
        annotations_by_unit[annotation.unit_id][annotation.rater_id] = annotation.classification

    rows: list[dict[str, object]] = []
    for unit in dataset.units:
        source = source_by_id[unit.source_id]
        record: dict[str, object] = {
            "Source": source.display_name,
            "Source role": "Aggregate" if source.is_aggregate else "Primary source",
            "Lexical unit": unit.lexical_unit,
            "Grammatical category": unit.grammatical_category,
        }
        present: list[Classification] = []
        for rater in dataset.raters:
            classification = annotations_by_unit.get(unit.unit_id, {}).get(
                rater.rater_id, Classification.MISSING
            )
            record[rater.display_name] = _classification_label(classification)
            if classification != Classification.MISSING:
                present.append(classification)
        distinct = set(present)
        if not present:
            state = "Missing"
        elif len(distinct) > 1:
            state = "Disagreement"
        else:
            state = "Agreement"
        record["Agreement state"] = state
        rows.append(record)
    return rows


def render_annotations() -> None:
    import pandas as pd
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY

    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    page_header(
        "Annotations",
        "Review validated rater decisions side by side.",
        (
            "Each row represents one lexical unit within a source. Rater columns show the validated "
            "semantic classification. Aggregate source rows remain visible as a separate source view."
        ),
    )
    semantic_legend()
    if dataset is None:
        st.info("Complete data validation first.", icon=":material/lock:")
        return

    records = annotation_records(dataset)
    dataframe = pd.DataFrame(records)
    rater_names = [rater.display_name for rater in dataset.raters]

    st.markdown("#### Explore annotations")
    filter_cols = st.columns((1.2, 1.2, 1, 1))
    source_options = sorted(dataframe["Source"].dropna().unique().tolist())
    category_options = sorted(dataframe["Grammatical category"].dropna().unique().tolist())
    selected_sources = filter_cols[0].multiselect(
        "Source", source_options, default=source_options, key="annotations_source_filter"
    )
    selected_categories = filter_cols[1].multiselect(
        "Grammatical category",
        category_options,
        default=category_options,
        key="annotations_category_filter",
    )
    agreement_state = filter_cols[2].selectbox(
        "Agreement state",
        ["All", "Agreement", "Disagreement", "Missing"],
        key="annotations_agreement_filter",
    )
    source_role = filter_cols[3].selectbox(
        "Source role",
        ["All", "Primary source", "Aggregate"],
        key="annotations_source_role_filter",
    )

    lower_cols = st.columns((1.35, 1))
    selected_raters = lower_cols[0].multiselect(
        "Raters shown", rater_names, default=rater_names, key="annotations_rater_filter"
    )
    search = lower_cols[1].text_input(
        "Search lexical unit", placeholder="Type a word or expression...", key="annotations_search"
    )

    filtered = dataframe.copy()
    if selected_sources:
        filtered = filtered[filtered["Source"].isin(selected_sources)]
    else:
        filtered = filtered.iloc[0:0]
    if selected_categories:
        filtered = filtered[filtered["Grammatical category"].isin(selected_categories)]
    else:
        filtered = filtered.iloc[0:0]
    if agreement_state != "All":
        filtered = filtered[filtered["Agreement state"] == agreement_state]
    if source_role != "All":
        filtered = filtered[filtered["Source role"] == source_role]
    if search.strip():
        filtered = filtered[
            filtered["Lexical unit"].astype(str).str.contains(search.strip(), case=False, na=False)
        ]

    fixed = ["Source", "Lexical unit", "Grammatical category"]
    visible_columns = fixed + selected_raters + ["Agreement state"]
    st.caption(f"Showing {len(filtered):,} lexical-unit rows.")
    st.dataframe(
        filtered[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=min(720, 92 + max(1, len(filtered)) * 35),
    )
