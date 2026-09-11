from __future__ import annotations

import html

import plotly.graph_objects as go

from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.review.service import build_review_cases
from metaphor_agreement_studio.review.types import ReviewCase, ReviewStatus
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.filters import default_reference_rater_id
from metaphor_agreement_studio.ui.legends import render_annotation_legend


REVIEW_HELP_TEXT = (
    "This workspace surfaces lexical units whose validated annotations differ across raters. "
    "A disagreement indicates a pattern that may deserve contextual review; it does not determine "
    "which rater is correct. Unanimous cases remain available as useful descriptive evidence."
)




def default_review_source_ids(dataset: ValidatedDataset) -> tuple[str, ...]:
    return tuple(source.source_id for source in dataset.sources if not source.is_aggregate)

def review_summary(cases: tuple[ReviewCase, ...]) -> dict[str, int]:
    disagreements = sum(case.status is ReviewStatus.DISAGREEMENT for case in cases)
    unanimous = sum(
        case.status in (ReviewStatus.UNANIMOUS_METAPHOR, ReviewStatus.UNANIMOUS_NON_METAPHOR)
        for case in cases
    )
    missing = sum(case.has_missing for case in cases)
    return {
        "requires_review": disagreements,
        "unanimous": unanimous,
        "with_missing": missing,
        "total": len(cases),
    }


def filter_review_cases(
    cases: tuple[ReviewCase, ...],
    *,
    mode: str = "All disagreements",
    focus_rater_id: str | None = None,
    source_ids: tuple[str, ...] | None = None,
    categories: tuple[str, ...] | None = None,
) -> tuple[ReviewCase, ...]:
    selected = list(cases)
    if mode == "All disagreements":
        selected = [case for case in selected if case.status is ReviewStatus.DISAGREEMENT]
    elif mode == "Focus rater differs":
        selected = [
            case
            for case in selected
            if focus_rater_id is not None and focus_rater_id in case.divergent_rater_ids
        ]
    elif mode == "Unanimous metaphor":
        selected = [case for case in selected if case.status is ReviewStatus.UNANIMOUS_METAPHOR]
    elif mode == "Unanimous non-metaphor":
        selected = [
            case for case in selected if case.status is ReviewStatus.UNANIMOUS_NON_METAPHOR
        ]
    elif mode == "Missing rating":
        selected = [case for case in selected if case.has_missing]
    elif mode != "All cases":
        raise ValueError(f"Unknown review filter mode: {mode}")

    if source_ids is not None:
        source_set = set(source_ids)
        selected = [case for case in selected if case.source_id in source_set]
    if categories is not None:
        category_set = set(categories)
        selected = [case for case in selected if case.grammatical_category in category_set]
    return tuple(selected)


def _case_y_label(case: ReviewCase) -> str:
    return f"{case.lexical_unit} · {case.grammatical_category}"


def build_annotation_map_figure(
    cases: tuple[ReviewCase, ...],
    dataset: ValidatedDataset,
    *,
    max_units: int = 40,
) -> go.Figure:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    shown = cases[:max_units]
    encoding = {
        Classification.METAPHOR: ("Metaphor", "circle", "#2F7D5B"),
        Classification.NON_METAPHOR: ("Non-metaphor", "circle-open", "#A65353"),
        Classification.MISSING: ("Missing / not rated", "x", "#8A9099"),
    }
    figure = go.Figure()
    for classification, (label, symbol, color) in encoding.items():
        x: list[str] = []
        y: list[str] = []
        custom: list[list[str]] = []
        for case in shown:
            for rater_id, value in case.rater_classifications:
                if value is classification:
                    x.append(names.get(rater_id, rater_id))
                    y.append(_case_y_label(case))
                    custom.append([case.source_display_name, case.lexical_unit])
        if x:
            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers",
                    name=label,
                    marker=dict(symbol=symbol, size=14, color=color, line=dict(width=2, color=color)),
                    customdata=custom,
                    hovertemplate=(
                        "%{customdata[1]}<br>%{x}: " + label +
                        "<br>Source: %{customdata[0]}<extra></extra>"
                    ),
                )
            )
    figure.update_layout(
        title="Annotation agreement map",
        xaxis_title="Rater",
        yaxis_title=None,
        yaxis=dict(autorange="reversed"),
        height=max(360, min(900, 120 + 27 * max(1, len(shown)))),
        margin=dict(l=40, r=30, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="Validated classification",
    )
    return figure


def _classification_visual(value: Classification) -> tuple[str, str]:
    if value is Classification.METAPHOR:
        return "●", "Metaphor"
    if value is Classification.NON_METAPHOR:
        return "○", "Non-metaphor"
    return "–", "Missing / not rated"


def _status_text(case: ReviewCase) -> str:
    if case.status is ReviewStatus.DISAGREEMENT:
        return "Requires review"
    if case.status in (ReviewStatus.UNANIMOUS_METAPHOR, ReviewStatus.UNANIMOUS_NON_METAPHOR):
        return "Unanimous agreement"
    return "No available ratings"


def render_review() -> None:
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY

    page_header(
        "Disagreement Review",
        "Inspect where raters converge, diverge, or leave annotations missing.",
        REVIEW_HELP_TEXT,
    )
    render_annotation_legend()
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return

    cases = build_review_cases(dataset)
    primary_source_ids = default_review_source_ids(dataset)
    primary_cases = filter_review_cases(cases, mode="All cases", source_ids=primary_source_ids)
    summary = review_summary(primary_cases)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Cases require review", summary["requires_review"])
    metric_cols[1].metric("Unanimous cases", summary["unanimous"])
    metric_cols[2].metric("Cases with missing ratings", summary["with_missing"])
    metric_cols[3].metric("Lexical units", summary["total"])

    control, workspace = st.columns((0.78, 2.22), gap="large")
    with control:
        st.markdown("#### Review filters")
        mode = st.selectbox(
            "Case type",
            (
                "All disagreements",
                "Focus rater differs",
                "Unanimous metaphor",
                "Unanimous non-metaphor",
                "Missing rating",
                "All cases",
            ),
            key="review_case_type",
        )
        rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
        rater_ids = tuple(rater_names)
        preferred = default_reference_rater_id(dataset)
        focus_index = rater_ids.index(preferred) if preferred in rater_ids else 0
        focus_rater_id = st.selectbox(
            "Focus rater",
            rater_ids,
            index=focus_index,
            format_func=lambda rater_id: rater_names[rater_id],
            key="review_focus_rater",
        )
        source_names = {source.source_id: source.display_name for source in dataset.sources}
        source_ids = tuple(source_names)
        selected_sources = tuple(
            st.multiselect(
                "Sources",
                source_ids,
                default=primary_source_ids,
                format_func=lambda source_id: source_names[source_id],
                key="review_sources",
            )
        )
        categories = tuple(sorted({unit.grammatical_category for unit in dataset.units}))
        selected_categories = tuple(
            st.multiselect(
                "Grammatical categories",
                categories,
                default=categories,
                key="review_categories",
            )
        )
        selected_cases = filter_review_cases(
            cases,
            mode=mode,
            focus_rater_id=focus_rater_id,
            source_ids=selected_sources,
            categories=selected_categories,
        )
        st.caption(f"{len(selected_cases)} cases in this view.")
        if mode == "Focus rater differs":
            st.info(
                f"This filter shows cases where {rater_names[focus_rater_id]} differs from the majority "
                "pattern. It does not imply that the focus rater is incorrect."
            )

    with workspace:
        st.markdown("#### Annotation pattern")
        if not selected_cases:
            st.info("No lexical units match the selected review filters.")
            return
        st.plotly_chart(
            build_annotation_map_figure(selected_cases, dataset),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        if len(selected_cases) > 40:
            st.caption("The map displays the first 40 cases in review priority order. All matching cases remain available below.")

        labels = {
            case.unit_id: f"{case.lexical_unit} · {case.grammatical_category} · {case.source_display_name}"
            for case in selected_cases
        }
        selected_unit_id = st.selectbox(
            "Inspect lexical unit",
            tuple(labels),
            format_func=lambda unit_id: labels[unit_id],
            key="review_selected_unit",
        )
        case = next(item for item in selected_cases if item.unit_id == selected_unit_id)
        status = _status_text(case)
        st.markdown(f"### {html.escape(case.lexical_unit)}")
        st.caption(f"{case.grammatical_category} · {case.source_display_name} · {status}")
        if case.context or case.verse:
            st.markdown("##### Context")
            st.info(case.context or case.verse)

        rater_columns = st.columns(max(1, len(case.rater_classifications)))
        for column, (rater_id, classification) in zip(
            rater_columns, case.rater_classifications, strict=True
        ):
            symbol, label = _classification_visual(classification)
            with column:
                st.markdown(f"**{rater_names.get(rater_id, rater_id)}**")
                st.markdown(f"{symbol} {label}")
        agreement = "—" if case.agreement_fraction is None else f"{case.agreement_fraction * 100:.1f}%"
        st.caption(f"Observed agreement within this unit: {agreement}")
        if case.majority_classification is not None and case.status is ReviewStatus.DISAGREEMENT:
            _, majority_label = _classification_visual(case.majority_classification)
            st.info(
                f"Majority pattern: {majority_label} ({max(case.metaphor_count, case.non_metaphor_count)} of "
                f"{case.available_ratings} available ratings). This is descriptive, not an adjudicated classification."
            )
        elif case.status in (ReviewStatus.UNANIMOUS_METAPHOR, ReviewStatus.UNANIMOUS_NON_METAPHOR):
            st.info("Unanimous agreement among all available ratings.")
            st.caption(
                "A no-variation subset can have 100% observed agreement while a chance-corrected coefficient is not estimable."
            )
