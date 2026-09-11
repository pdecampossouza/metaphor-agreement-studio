from __future__ import annotations

from dataclasses import replace

import pandas as pd
import plotly.graph_objects as go

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.types import AnalysisBundle, AnalysisConfig, EstimateStatus
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.filters import AnalysisSelection, render_analysis_filters
from metaphor_agreement_studio.ui.legends import render_annotation_legend
from metaphor_agreement_studio.ui.metric_components import render_metric_result


AGREEMENT_SECTION_TITLES = (
    "Observed agreement",
    "Pairwise agreement",
    "Overall multi-rater agreement",
    "Rater classification tendency",
    "Specific agreement",
)
COCHRAN_Q_HELP = (
    "Cochran's Q is not an agreement coefficient. It tests whether raters differ in how frequently "
    "they classify units as metaphorical."
)


def _selected_units(dataset: ValidatedDataset, selection: AnalysisSelection) -> tuple[str, ...]:
    source_ids = set(selection.source_ids)
    categories = set(selection.categories)
    return tuple(
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in source_ids and unit.grammatical_category in categories
    )


def rater_tendency_records(
    dataset: ValidatedDataset,
    selection: AnalysisSelection,
) -> list[dict[str, object]]:
    unit_ids = set(_selected_units(dataset, selection))
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for rater_id in selection.rater_ids:
        values = [
            annotation.classification
            for annotation in dataset.annotations
            if annotation.rater_id == rater_id and annotation.unit_id in unit_ids
        ]
        available = [value for value in values if value is not Classification.MISSING]
        metaphor = sum(value is Classification.METAPHOR for value in available)
        rate = 0.0 if not available else metaphor / len(available)
        rows.append(
            {
                "Rater ID": rater_id,
                "Rater": names.get(rater_id, rater_id),
                "Metaphor rate": rate,
                "Metaphor count": metaphor,
                "Effective N": len(available),
            }
        )
    return rows


def build_pairwise_kappa_matrix(bundle: AnalysisBundle, dataset: ValidatedDataset) -> pd.DataFrame:
    rater_ids = tuple(
        rater.rater_id
        for rater in dataset.raters
        if not bundle.config.selected_rater_ids or rater.rater_id in bundle.config.selected_rater_ids
    )
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    labels = [names[rater_id] for rater_id in rater_ids]
    matrix = pd.DataFrame(index=labels, columns=labels, dtype=float)
    for label in labels:
        matrix.loc[label, label] = 1.0
    for pair in bundle.pairwise:
        left = names[pair.rater_a_id]
        right = names[pair.rater_b_id]
        if pair.kappa.value is not None:
            matrix.loc[left, right] = pair.kappa.value
            matrix.loc[right, left] = pair.kappa.value
    return matrix


def build_pairwise_kappa_figure(bundle: AnalysisBundle, dataset: ValidatedDataset) -> go.Figure:
    matrix = build_pairwise_kappa_matrix(bundle, dataset)
    text = matrix.map(lambda value: "—" if pd.isna(value) else f"{value:.2f}").values
    figure = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            zmin=-1,
            zmax=1,
            zmid=0,
            colorscale=[
                [0.0, "#6B7280"],
                [0.5, "#F3F4F6"],
                [1.0, "#315E8A"],
            ],
            text=text,
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}<br>Cohen's κ = %{z:.3f}<extra></extra>",
            colorbar=dict(title="κ", thickness=12),
        )
    )
    figure.update_layout(
        title="Pairwise Cohen's κ matrix",
        xaxis_title=None,
        yaxis_title=None,
        height=max(340, 80 + 58 * len(matrix)),
        margin=dict(l=40, r=40, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def build_rater_tendency_figure(records: list[dict[str, object]]) -> go.Figure:
    figure = go.Figure(
        data=go.Bar(
            x=[record["Rater"] for record in records],
            y=[float(record["Metaphor rate"]) * 100 for record in records],
            text=[f"{float(record['Metaphor rate']) * 100:.1f}%" for record in records],
            textposition="outside",
            marker_color="#315E8A",
            customdata=[record["Effective N"] for record in records],
            hovertemplate="%{x}<br>Metaphor rate: %{y:.1f}%<br>Effective N: %{customdata}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Metaphor classification rate by rater",
        yaxis_title="Classified as metaphor (%)",
        yaxis_range=[0, 105],
        xaxis_title=None,
        height=360,
        margin=dict(l=40, r=30, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def _pairwise_rows(bundle: AnalysisBundle, dataset: ValidatedDataset) -> list[dict[str, object]]:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows = []
    for pair in bundle.pairwise:
        rows.append(
            {
                "Rater pair": f"{names[pair.rater_a_id]} × {names[pair.rater_b_id]}",
                "Effective N": pair.kappa.effective_n,
                "Observed agreement": (
                    "—" if pair.raw_agreement.value is None else f"{pair.raw_agreement.value * 100:.1f}%"
                ),
                "Cohen's κ": "Not estimable" if pair.kappa.value is None else f"{pair.kappa.value:.3f}",
                "Status": pair.kappa.status.value.replace("_", " ").title(),
            }
        )
    return rows


def _specific_figure(bundle: AnalysisBundle, dataset: ValidatedDataset) -> go.Figure:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    pair_labels = [f"{names[item.rater_a_id]} × {names[item.rater_b_id]}" for item in bundle.specific_agreement]
    metaphor = [
        None if item.metaphor_agreement.value is None else item.metaphor_agreement.value * 100
        for item in bundle.specific_agreement
    ]
    non_metaphor = [
        None if item.non_metaphor_agreement.value is None else item.non_metaphor_agreement.value * 100
        for item in bundle.specific_agreement
    ]
    figure = go.Figure()
    figure.add_bar(name="Metaphor agreement", x=pair_labels, y=metaphor, marker_color="#3A6EA5")
    figure.add_bar(name="Non-metaphor agreement", x=pair_labels, y=non_metaphor, marker_color="#7A7F87")
    figure.update_layout(
        title="Class-specific agreement",
        barmode="group",
        yaxis_title="Agreement (%)",
        yaxis_range=[0, 105],
        height=380,
        margin=dict(l=40, r=30, t=70, b=70),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    return figure


def _analysis_config(selection: AnalysisSelection) -> AnalysisConfig:
    return AnalysisConfig(
        selected_source_ids=selection.source_ids,
        selected_categories=selection.categories,
        selected_rater_ids=selection.rater_ids,
    )


def render_agreement() -> None:
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY, set_route
    from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
    from metaphor_agreement_studio.ui.navigation import Route

    page_header(
        "Agreement",
        "Pairwise and overall inter-rater agreement.",
        (
            "Start with observed agreement, then use chance-corrected coefficients to examine consistency. "
            "Cochran's Q is shown separately because it tests rater classification tendency rather than agreement. "
            "Use the filters to inspect a source, grammatical category, or subset of raters."
        ),
    )
    render_annotation_legend()
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return

    selection = render_analysis_filters(dataset, "agreement")
    if len(selection.rater_ids) < 2 or not selection.source_ids or not selection.categories:
        st.info("Select at least two raters, one source and one grammatical category to analyse agreement.")
        return

    config = _analysis_config(selection)
    cache_key = (dataset.dataset_id, config)
    cache = st.session_state.get("phase4_agreement_cache")
    if cache is not None and cache[0] == cache_key:
        bundle = cache[1]
    else:
        with st.spinner("Calculating agreement for the selected validated annotations..."):
            bundle = analyze_dataset_cached(dataset, config)
        st.session_state["phase4_agreement_cache"] = (cache_key, bundle)

    st.markdown("#### Observed agreement")
    st.caption("Observed agreement is the share of paired classifications that are identical. It is shown before chance-corrected statistics.")
    if len(bundle.pairwise) == 1:
        pair = bundle.pairwise[0]
        cols = st.columns((1, 1, 2))
        with cols[0]:
            render_metric_result("Observed agreement", pair.raw_agreement, percent=True)
        with cols[1]:
            st.metric("Shared lexical units", pair.raw_agreement.effective_n)
        with cols[2]:
            st.caption("This is the most direct description of how often the two selected raters made the same decision.")
    else:
        agreement_values = [pair.raw_agreement.value for pair in bundle.pairwise if pair.raw_agreement.value is not None]
        mean_agreement = sum(agreement_values) / len(agreement_values) if agreement_values else None
        st.metric("Mean pairwise observed agreement", "—" if mean_agreement is None else f"{mean_agreement * 100:.1f}%")

    st.markdown("#### Pairwise agreement")
    st.caption("Cohen's Kappa compares two raters at a time and corrects observed agreement for agreement expected by chance.")
    chart_col, table_col = st.columns((1.05, 1.2), gap="large")
    with chart_col:
        st.plotly_chart(build_pairwise_kappa_figure(bundle, dataset), use_container_width=True, config={"displayModeBar": False})
    with table_col:
        st.dataframe(pd.DataFrame(_pairwise_rows(bundle, dataset)), use_container_width=True, hide_index=True)
        pair_options = {
            row["Rater pair"]: pair
            for row, pair in zip(_pairwise_rows(bundle, dataset), bundle.pairwise, strict=True)
        }
        selected_pair_label = st.selectbox("Inspect a rater pair", tuple(pair_options), key="agreement_pair_drilldown")
        if st.button("Open pair in Annotations", icon=":material/table_view:", key="agreement_open_pair"):
            pair = pair_options[selected_pair_label]
            names = {rater.rater_id: rater.display_name for rater in dataset.raters}
            st.session_state["annotations_rater_filter"] = [names[pair.rater_a_id], names[pair.rater_b_id]]
            set_route(Route.ANNOTATIONS)
            st.rerun()

    if bundle.overall_multirater:
        st.markdown("#### Overall multi-rater agreement")
        st.caption("These measures summarize agreement across all selected raters. Cohen's Kappa remains pairwise only.")
        columns = st.columns(len(bundle.overall_multirater))
        labels = {"fleiss_kappa": "Fleiss' Kappa", "krippendorff_alpha": "Krippendorff's Alpha"}
        for column, metric in zip(columns, bundle.overall_multirater, strict=True):
            with column:
                render_metric_result(labels.get(metric.metric, metric.metric), metric)

    st.markdown("#### Rater classification tendency")
    st.caption(COCHRAN_Q_HELP)
    q = bundle.cochran_q
    left, right = st.columns((0.8, 1.5), gap="large")
    with left:
        if q is None:
            st.info("Cochran's Q requires at least two selected raters.")
        else:
            q_value = "Not estimable" if q.q is None else f"{q.q:.3f}"
            st.metric("Cochran's Q", q_value)
            st.caption(
                f"df: {'—' if q.degrees_of_freedom is None else q.degrees_of_freedom} · "
                f"p: {'—' if q.p_value is None else ('< .001' if q.p_value < .001 else f'{q.p_value:.3f}')} · "
                f"Effective N: {q.effective_n}"
            )
            if q.status is not EstimateStatus.OK:
                st.info(q.status.value.replace("_", " ").title())
    with right:
        tendency = rater_tendency_records(dataset, selection)
        st.plotly_chart(build_rater_tendency_figure(tendency), use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Specific agreement")
    st.caption("Metaphor and non-metaphor agreement are shown separately because raters may agree differently across the two classes.")
    st.plotly_chart(_specific_figure(bundle, dataset), use_container_width=True, config={"displayModeBar": False})

    if st.button("View underlying annotations", icon=":material/arrow_forward:", key="agreement_underlying_annotations"):
        set_route(Route.ANNOTATIONS)
        st.rerun()
