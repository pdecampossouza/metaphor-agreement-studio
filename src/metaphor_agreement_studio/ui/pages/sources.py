from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, GroupResult
from metaphor_agreement_studio.ui.components import page_header


def split_source_groups(
    groups: tuple[GroupResult, ...],
    dataset: ValidatedDataset,
) -> tuple[tuple[GroupResult, ...], tuple[GroupResult, ...]]:
    aggregate_ids = {source.source_id for source in dataset.sources if source.is_aggregate}
    primary = tuple(group for group in groups if group.group_id not in aggregate_ids)
    aggregate = tuple(group for group in groups if group.group_id in aggregate_ids)
    return primary, aggregate


def _pair_for_group(group: GroupResult, pair_ids: tuple[str, str]):
    wanted = set(pair_ids)
    for pair in group.pairwise:
        if {pair.rater_a_id, pair.rater_b_id} == wanted:
            return pair
    return None


def _format_p(value: float | None) -> str:
    if value is None:
        return "—"
    return "< .001" if value < 0.001 else f"{value:.3f}"


def source_overview_records(
    groups: tuple[GroupResult, ...],
    dataset: ValidatedDataset,
    pair_ids: tuple[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in groups:
        pair = _pair_for_group(group, pair_ids)
        if pair is None:
            continue
        q = group.cochran_q
        fleiss_value = group.fleiss_kappa.value if group.fleiss_kappa is not None else None
        if group.fleiss_kappa is None:
            fleiss_display = "—"
        elif fleiss_value is None:
            fleiss_display = group.fleiss_kappa.status.value.replace("_", " ").title()
        else:
            fleiss_display = f"{fleiss_value:.3f}"
        rows.append(
            {
                "Source": group.display_name,
                "N": group.lexical_unit_count,
                "Raw agreement": "—" if pair.raw_agreement.value is None else f"{pair.raw_agreement.value * 100:.1f}%",
                "Cohen's κ": "Not estimable" if pair.kappa.value is None else f"{pair.kappa.value:.3f}",
                "Fleiss' κ": fleiss_display,
                "Cochran Q": "—" if q is None or q.q is None else f"{q.q:.3f}",
                "Q p-value": "—" if q is None else _format_p(q.p_value),
                "_raw_value": pair.raw_agreement.value,
                "_kappa_value": pair.kappa.value,
                "_fleiss_value": fleiss_value,
                "_source_id": group.group_id,
            }
        )
    return rows


def build_source_agreement_figure(rows: list[dict[str, object]]) -> go.Figure:
    labels = [f"{row['Source']} (n={row['N']})" for row in rows]
    values = [None if row["_raw_value"] is None else float(row["_raw_value"]) * 100 for row in rows]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color="#315E8A",
            text=["—" if value is None else f"{value:.1f}%" for value in values],
            textposition="outside",
            hovertemplate="%{x}<br>Observed agreement: %{y:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title="Observed agreement by source",
        yaxis_title="Observed agreement (%)",
        yaxis_range=[0, 105],
        xaxis_title=None,
        height=390,
        margin=dict(l=40, r=30, t=70, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def build_source_kappa_figure(rows: list[dict[str, object]]) -> go.Figure:
    labels = [f"{row['Source']} (n={row['N']})" for row in rows if row["_kappa_value"] is not None]
    values = [float(row["_kappa_value"]) for row in rows if row["_kappa_value"] is not None]
    figure = go.Figure(
        go.Scatter(
            x=labels,
            y=values,
            mode="markers+text",
            marker=dict(size=13, color="#315E8A"),
            text=[f"κ {value:.2f}" for value in values],
            textposition="top center",
            hovertemplate="%{x}<br>Cohen's κ = %{y:.3f}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#9CA3AF")
    figure.update_layout(
        title="Cohen's κ by source",
        yaxis_title="Cohen's κ",
        yaxis_range=[-1.05, 1.08],
        height=390,
        margin=dict(l=40, r=30, t=70, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def build_source_fleiss_figure(rows: list[dict[str, object]]) -> go.Figure:
    usable = [row for row in rows if row.get("_fleiss_value") is not None]
    labels = [f"{row['Source']} (n={row['N']})" for row in usable]
    values = [float(row["_fleiss_value"]) for row in usable]
    figure = go.Figure(
        go.Scatter(
            x=labels,
            y=values,
            mode="markers+text",
            marker=dict(size=13, color="#315E8A", symbol="diamond"),
            text=[f"κ {value:.2f}" for value in values],
            textposition="top center",
            hovertemplate="%{x}<br>Fleiss' κ = %{y:.3f}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#9CA3AF")
    figure.update_layout(
        title="Fleiss' κ by source",
        yaxis_title="Fleiss' κ",
        yaxis_range=[-1.05, 1.08],
        height=390,
        margin=dict(l=40, r=30, t=70, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def render_sources() -> None:
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY, set_route
    from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
    from metaphor_agreement_studio.ui.navigation import Route

    page_header(
        "Source Groups",
        "Compare agreement across source tables, videos, or future songs.",
        (
            "Primary sources are compared independently. Aggregate sources are shown separately so their lexical "
            "units are never silently added to the primary-source total."
        ),
    )
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return

    bundle = analyze_dataset_cached(dataset, AnalysisConfig())
    primary, aggregate = split_source_groups(bundle.by_source, dataset)
    if not bundle.pairwise:
        st.info("At least two raters are required for source agreement comparisons.")
        return
    rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    pair_options = {
        f"{rater_names[pair.rater_a_id]} × {rater_names[pair.rater_b_id]}": (
            pair.rater_a_id,
            pair.rater_b_id,
        )
        for pair in bundle.pairwise
    }
    selected_pair = st.selectbox("Rater pair", tuple(pair_options), key="source_pair")
    pair_ids = pair_options[selected_pair]
    primary_rows = source_overview_records(primary, dataset, pair_ids)

    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        st.plotly_chart(build_source_agreement_figure(primary_rows), use_container_width=True, config={"displayModeBar": False})
    with chart_right:
        if len(dataset.raters) >= 3:
            st.plotly_chart(build_source_fleiss_figure(primary_rows), use_container_width=True, config={"displayModeBar": False})
        else:
            st.plotly_chart(build_source_kappa_figure(primary_rows), use_container_width=True, config={"displayModeBar": False})
    if len(dataset.raters) >= 3:
        st.caption("Fleiss' κ is the global agreement coefficient within each source for three or more raters. Pairwise Cohen's κ remains available below.")
        st.plotly_chart(build_source_kappa_figure(primary_rows), use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Primary sources")
    display_primary = [{key: value for key, value in row.items() if not key.startswith("_")} for row in primary_rows]
    st.dataframe(pd.DataFrame(display_primary), use_container_width=True, hide_index=True)
    st.caption(f"Primary-source total: {sum(group.lexical_unit_count for group in primary)} lexical units.")

    aggregate_rows = source_overview_records(aggregate, dataset, pair_ids)
    if aggregate_rows:
        st.markdown("#### Overall / aggregate views")
        st.info("Aggregate sources are views over material already represented in primary sources. Their N is not added to the primary-source total.")
        display_aggregate = [{key: value for key, value in row.items() if not key.startswith("_")} for row in aggregate_rows]
        st.dataframe(pd.DataFrame(display_aggregate), use_container_width=True, hide_index=True)

    all_rows = primary_rows + aggregate_rows
    selected_source = st.selectbox(
        "Inspect source",
        tuple(row["Source"] for row in all_rows),
        key="source_detail",
    )
    row = next(item for item in all_rows if item["Source"] == selected_source)
    st.markdown(f"#### {selected_source}")
    cohen_kappa = row["Cohen's κ"]
    fleiss_kappa = row["Fleiss' κ"]
    st.caption(
        f"N = {row['N']} · Observed agreement = {row['Raw agreement']} · Cohen's κ = {cohen_kappa} · "
        f"Fleiss' κ = {fleiss_kappa} · Cochran's Q = {row['Cochran Q']} · p = {row['Q p-value']}"
    )
    if st.button("Open source in Annotations", icon=":material/table_view:", key="source_annotations"):
        st.session_state["annotations_source_filter"] = [selected_source]
        set_route(Route.ANNOTATIONS)
        st.rerun()
