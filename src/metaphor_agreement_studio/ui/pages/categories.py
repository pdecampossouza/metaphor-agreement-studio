from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig, GroupResult
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.filters import AnalysisSelection, render_analysis_filters


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


def _pair_label(dataset: ValidatedDataset, pair_ids: tuple[str, str]) -> str:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    return f"{names.get(pair_ids[0], pair_ids[0])} × {names.get(pair_ids[1], pair_ids[1])}"


def category_overview_records(
    groups: tuple[GroupResult, ...],
    dataset: ValidatedDataset,
    pair_ids: tuple[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pair_label = _pair_label(dataset, pair_ids)
    for group in groups:
        pair = _pair_for_group(group, pair_ids)
        if pair is None:
            continue
        raw_value = pair.raw_agreement.value
        kappa_value = pair.kappa.value
        if group.lexical_unit_count <= 1:
            kappa_display = "Descriptive result only"
            kappa_value = None
        elif kappa_value is None:
            kappa_display = "Not estimable"
        else:
            kappa_display = f"{kappa_value:.3f}"
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
                "Category": group.display_name,
                "N": group.lexical_unit_count,
                "Pairwise observed agreement": "—" if raw_value is None else f"{raw_value * 100:.1f}%",
                "Cohen's κ": kappa_display,
                "Fleiss' κ": fleiss_display,
                "Cochran Q": "—" if q is None or q.q is None else f"{q.q:.3f}",
                "Q p-value": "—" if q is None else _format_p(q.p_value),
                "_raw_value": raw_value,
                "_kappa_value": kappa_value,
                "_fleiss_value": fleiss_value,
                "_pair_label": pair_label,
            }
        )
    return rows


def build_category_agreement_figure(rows: list[dict[str, object]]) -> go.Figure:
    labels = [f"{row['Category']} (n={row['N']})" for row in rows]
    values = [None if row["_raw_value"] is None else float(row["_raw_value"]) * 100 for row in rows]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color="#315E8A",
            text=["—" if value is None else f"{value:.1f}%" for value in values],
            textposition="outside",
            hovertemplate="%{y}<br>Pairwise observed agreement: %{x:.1f}%<extra></extra>",
        )
    )
    pair_label = rows[0].get("_pair_label") if rows else None
    title = "Pairwise observed agreement by grammatical category"
    if pair_label:
        title = f"{title} — {pair_label}"
    figure.update_layout(
        title=title,
        xaxis_title="Pairwise observed agreement (%)",
        xaxis_range=[0, 105],
        yaxis=dict(autorange="reversed"),
        height=max(360, 90 + 42 * max(1, len(rows))),
        margin=dict(l=40, r=40, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def build_category_kappa_figure(rows: list[dict[str, object]]) -> go.Figure:
    usable = [row for row in rows if row["_kappa_value"] is not None]
    labels = [f"{row['Category']} (n={row['N']})" for row in usable]
    values = [float(row["_kappa_value"]) for row in usable]
    figure = go.Figure(
        go.Scatter(
            x=values,
            y=labels,
            mode="markers+text",
            marker=dict(size=13, color="#315E8A"),
            text=[f"κ {value:.2f}" for value in values],
            textposition="middle right",
            hovertemplate="%{y}<br>Cohen's κ = %{x:.3f}<extra></extra>",
        )
    )
    figure.add_vline(x=0, line_dash="dot", line_color="#9CA3AF")
    figure.update_layout(
        title="Cohen's κ by grammatical category",
        xaxis_title="Cohen's κ",
        xaxis_range=[-1.05, 1.08],
        yaxis=dict(autorange="reversed"),
        height=max(360, 90 + 42 * max(1, len(usable))),
        margin=dict(l=40, r=60, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def build_category_fleiss_figure(rows: list[dict[str, object]]) -> go.Figure:
    usable = [row for row in rows if row.get("_fleiss_value") is not None]
    labels = [f"{row['Category']} (n={row['N']})" for row in usable]
    values = [float(row["_fleiss_value"]) for row in usable]
    figure = go.Figure(
        go.Scatter(
            x=values,
            y=labels,
            mode="markers+text",
            marker=dict(size=13, color="#315E8A", symbol="diamond"),
            text=[f"κ {value:.2f}" for value in values],
            textposition="middle right",
            hovertemplate="%{y}<br>Fleiss' κ = %{x:.3f}<extra></extra>",
        )
    )
    figure.add_vline(x=0, line_dash="dot", line_color="#9CA3AF")
    figure.update_layout(
        title="Fleiss' κ by grammatical category",
        xaxis_title="Fleiss' κ",
        xaxis_range=[-1.05, 1.08],
        yaxis=dict(autorange="reversed"),
        height=max(360, 90 + 42 * max(1, len(usable))),
        margin=dict(l=40, r=60, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def rater_counts_for_category(
    dataset: ValidatedDataset,
    category: str,
    selection: AnalysisSelection,
) -> pd.DataFrame:
    source_ids = set(selection.source_ids)
    selected_raters = set(selection.rater_ids)
    unit_ids = {
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in source_ids and unit.grammatical_category == category
    }
    rows = []
    for rater in dataset.raters:
        if rater.rater_id not in selected_raters:
            continue
        values = [
            annotation.classification
            for annotation in dataset.annotations
            if annotation.rater_id == rater.rater_id and annotation.unit_id in unit_ids
        ]
        rows.append(
            {
                "Rater": rater.display_name,
                "Metaphor": sum(value is Classification.METAPHOR for value in values),
                "Non-metaphor": sum(value is Classification.NON_METAPHOR for value in values),
                "Missing": len(unit_ids) - sum(value is not Classification.MISSING for value in values),
            }
        )
    return pd.DataFrame(rows)


def render_categories() -> None:
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY, set_route
    from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
    from metaphor_agreement_studio.ui.navigation import Route

    page_header(
        "Grammatical Categories",
        "Compare inter-rater agreement across parts of speech.",
        (
            "Each grammatical category is analysed as its own subset. Always interpret a coefficient together "
            "with the number of lexical units (N); small categories can produce unstable or non-estimable values."
        ),
    )
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return

    selection = render_analysis_filters(dataset, "category")
    if len(selection.rater_ids) < 2 or not selection.source_ids or not selection.categories:
        st.info("Select at least two raters, one source and one grammatical category to compare categories.")
        return

    config = AnalysisConfig(
        selected_source_ids=selection.source_ids,
        selected_categories=selection.categories,
        selected_rater_ids=selection.rater_ids,
    )
    bundle = analyze_dataset_cached(dataset, config)
    pair_options = {
        f"{next(r.display_name for r in dataset.raters if r.rater_id == pair.rater_a_id)} × "
        f"{next(r.display_name for r in dataset.raters if r.rater_id == pair.rater_b_id)}": (
            pair.rater_a_id,
            pair.rater_b_id,
        )
        for pair in bundle.pairwise
    }
    if not pair_options:
        st.info("At least two raters are required for category agreement comparisons.")
        return
    selected_pair_label = st.selectbox("Rater pair", tuple(pair_options), key="category_pair")
    pair_ids = pair_options[selected_pair_label]
    rows = category_overview_records(bundle.by_category, dataset, pair_ids)
    if not rows:
        st.info("No lexical units match the selected analysis filters.")
        return

    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(build_category_agreement_figure(rows), use_container_width=True, config={"displayModeBar": False})
    with right:
        if len(selection.rater_ids) >= 3:
            st.plotly_chart(build_category_fleiss_figure(rows), use_container_width=True, config={"displayModeBar": False})
        else:
            st.plotly_chart(build_category_kappa_figure(rows), use_container_width=True, config={"displayModeBar": False})
    if len(selection.rater_ids) >= 3:
        st.caption("Fleiss' κ is the global agreement coefficient within each category for three or more raters. Pairwise Cohen's κ remains available below.")
        st.plotly_chart(build_category_kappa_figure(rows), use_container_width=True, config={"displayModeBar": False})

    display_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]
    st.markdown("#### Category overview")
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

    selected_category = st.selectbox(
        "Inspect category",
        tuple(row["Category"] for row in rows),
        key="category_detail",
    )
    row = next(item for item in rows if item["Category"] == selected_category)
    st.markdown(f"#### {selected_category}")
    cohen_kappa = row["Cohen's κ"]
    fleiss_kappa = row["Fleiss' κ"]
    st.caption(
        f"N = {row['N']} lexical units · Pairwise observed agreement ({row['_pair_label']}) = "
        f"{row['Pairwise observed agreement']} · "
        f"Cohen's κ = {cohen_kappa} · Fleiss' κ = {fleiss_kappa}"
    )
    if int(row["N"]) <= 1:
        st.info("Descriptive result only. This category contains one lexical unit, so inferential agreement statistics are not informative.")
    st.dataframe(
        rater_counts_for_category(dataset, selected_category, selection),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Cochran's Q: {row['Cochran Q']} · p-value: {row['Q p-value']}")
    if st.button("Open category in Annotations", icon=":material/table_view:", key="category_annotations"):
        source_names = {source.source_id: source.display_name for source in dataset.sources}
        rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
        st.session_state["annotations_source_filter"] = [
            source_names[source_id] for source_id in selection.source_ids
        ]
        st.session_state["annotations_category_filter"] = [selected_category]
        st.session_state["annotations_rater_filter"] = [
            rater_names[rater_id] for rater_id in selection.rater_ids
        ]
        set_route(Route.ANNOTATIONS)
        st.rerun()
