from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.review.service import build_rater_profile
from metaphor_agreement_studio.statistics.types import AnalysisBundle, AnalysisConfig, AnalysisPerspective
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.filters import default_analysis_selection, default_reference_rater_id


DIVERGENCE_EXPLANATION = (
    "Lower agreement indicates greater divergence from the other raters; "
    "it does not indicate that a rater is incorrect."
)


def suggested_focus_rater_id(dataset: ValidatedDataset) -> str | None:
    preferred = default_reference_rater_id(dataset)
    if preferred is not None:
        return preferred
    return dataset.raters[0].rater_id if dataset.raters else None


def focus_pairwise_records(
    bundle: AnalysisBundle,
    dataset: ValidatedDataset,
    focus_rater_id: str,
) -> list[dict[str, object]]:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for pair in bundle.pairwise:
        if focus_rater_id not in (pair.rater_a_id, pair.rater_b_id):
            continue
        other_id = pair.rater_b_id if pair.rater_a_id == focus_rater_id else pair.rater_a_id
        raw = pair.raw_agreement.value
        kappa = pair.kappa.value
        rows.append(
            {
                "Compared with": names.get(other_id, other_id),
                "Effective N": pair.kappa.effective_n,
                "Observed agreement": "—" if raw is None else f"{raw * 100:.1f}%",
                "Cohen's κ": "Not estimable" if kappa is None else f"{kappa:.3f}",
                "_kappa_value": kappa,
                "_raw_value": raw,
                "_other_id": other_id,
            }
        )
    return rows


def build_focus_kappa_figure(rows: list[dict[str, object]], focus_name: str) -> go.Figure:
    usable = [row for row in rows if row["_kappa_value"] is not None]
    figure = go.Figure(
        go.Bar(
            x=[row["Compared with"] for row in usable],
            y=[float(row["_kappa_value"]) for row in usable],
            marker_color="#315E8A",
            text=[f"κ {float(row['_kappa_value']):.2f}" for row in usable],
            textposition="outside",
            customdata=[row["Effective N"] for row in usable],
            hovertemplate="%{x}<br>Cohen's κ = %{y:.3f}<br>Effective N: %{customdata}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#9CA3AF")
    figure.update_layout(
        title=f"{focus_name}: pairwise Cohen's κ",
        xaxis_title="Compared rater",
        yaxis_title="Cohen's κ",
        yaxis_range=[-1.05, 1.08],
        height=390,
        margin=dict(l=40, r=30, t=70, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def render_rater_explorer() -> None:
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY, set_route
    from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
    from metaphor_agreement_studio.ui.navigation import Route
    from metaphor_agreement_studio.ui.pages.agreement import (
        build_rater_tendency_figure,
        rater_tendency_records,
    )

    page_header(
        "Rater Explorer",
        "Explore one rater's annotation pattern in relation to the others.",
        (
            "Select any rater as the focus. The page summarizes pairwise agreement and descriptive divergence "
            "patterns without treating the focus rater as correct or incorrect. Bráulio is suggested when present "
            "because he is the study expert, but the selection remains fully changeable."
        ),
    )
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return
    if not dataset.raters:
        st.info("No raters are available in this validated dataset.")
        return

    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rater_ids = tuple(names)
    suggested = suggested_focus_rater_id(dataset)
    default_index = rater_ids.index(suggested) if suggested in rater_ids else 0
    focus_rater_id = st.selectbox(
        "Focus rater",
        rater_ids,
        index=default_index,
        format_func=lambda rater_id: names[rater_id],
        key="rater_explorer_focus",
    )
    focus_name = names[focus_rater_id]

    bundle = analyze_dataset_cached(
        dataset,
        AnalysisConfig(
            analysis_perspective=AnalysisPerspective.REFERENCE_RATER,
            reference_rater_id=focus_rater_id,
        ),
    )
    profile = build_rater_profile(dataset, focus_rater_id, bundle)
    metrics = st.columns(4)
    metrics[0].metric("Metaphor classification rate", f"{profile.metaphor_rate * 100:.1f}%")
    metrics[1].metric(
        "Mean pairwise Cohen's κ",
        "Not estimable" if profile.mean_pairwise_kappa is None else f"{profile.mean_pairwise_kappa:.3f}",
    )
    metrics[2].metric("Differs from all other raters", profile.differs_from_all_count)
    metrics[3].metric("Agrees with majority pattern", profile.agrees_with_majority_count)
    st.caption(DIVERGENCE_EXPLANATION)

    pair_rows = focus_pairwise_records(bundle, dataset, focus_rater_id)
    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(
            build_focus_kappa_figure(pair_rows, focus_name),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with right:
        tendency = rater_tendency_records(dataset, default_analysis_selection(dataset))
        st.plotly_chart(
            build_rater_tendency_figure(tendency),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    st.markdown("#### Pairwise comparisons")
    display_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in pair_rows]
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

    info_col, annotation_col, action_col = st.columns((2, 1, 1))
    with info_col:
        st.info(
            f"{focus_name} is the current focus rater. Selecting a focus changes presentation only; it does not "
            "change the original annotations or define a gold standard."
        )
    with annotation_col:
        if st.button(
            "Open focus rater in Annotations",
            icon=":material/table_view:",
            key="rater_explorer_annotations",
        ):
            st.session_state["annotations_rater_filter"] = [focus_name]
            set_route(Route.ANNOTATIONS)
            st.rerun()
    with action_col:
        if st.button(
            "Use as expert benchmark",
            icon=":material/workspace_premium:",
            key="rater_explorer_expert",
        ):
            st.session_state["phase3_analysis_perspective"] = "Expert benchmark"
            st.session_state["phase3_reference_rater"] = focus_rater_id
            set_route(Route.STATISTICS)
            st.rerun()
