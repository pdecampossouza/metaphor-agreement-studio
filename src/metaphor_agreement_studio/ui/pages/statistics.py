from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.persistence.project_service import record_analysis_version
from metaphor_agreement_studio.state.session import (
    ANALYSIS_VERSION_KEY,
    DATASET_VERSION_KEY,
    PROJECT_CONTEXT_KEY,
    PROJECT_NAME_KEY,
    WORKSPACE_MODE_KEY,
    set_project_context,
)
from metaphor_agreement_studio.statistics.explanations import explanation_text
from metaphor_agreement_studio.statistics.types import (
    AnalysisBundle,
    AnalysisConfig,
    AnalysisPerspective,
    EstimateStatus,
    GroupResult,
    MetricResult,
)
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.filters import (
    AnalysisSelection,
    default_reference_rater_id as _default_reference_rater_id,
    render_analysis_filters,
)


def persist_analysis_if_project(state, config):
    if state.get(WORKSPACE_MODE_KEY) != "research_project":
        return None
    context = state.get(PROJECT_CONTEXT_KEY)
    if context is None:
        return None
    updated = record_analysis_version(context, config)
    set_project_context(updated, state)
    return updated


def build_report_analysis_config(
    base_config: AnalysisConfig, selected_rater_ids: tuple[str, ...]
) -> AnalysisConfig:
    """Return the report-specific analysis scope without changing the on-screen analysis."""
    return replace(base_config, selected_rater_ids=tuple(selected_rater_ids))


def build_comparison_report_download(
    dataset: ValidatedDataset,
    bundle: AnalysisBundle,
    state,
    *,
    category_association=None,
) -> tuple[str, bytes]:
    from metaphor_agreement_studio.reporting.comparison_pdf import (
        ComparisonReportMetadata,
        build_comparison_report_pdf,
        comparison_report_filename,
    )

    metadata = ComparisonReportMetadata(
        project_name=str(state.get(PROJECT_NAME_KEY) or "Quick Analysis"),
        dataset_version=state.get(DATASET_VERSION_KEY),
        analysis_version=state.get(ANALYSIS_VERSION_KEY),
    )
    payload = build_comparison_report_pdf(
        dataset, bundle, metadata, category_association=category_association
    )
    return comparison_report_filename(metadata), payload


_STATUS_LABELS = {
    EstimateStatus.OK: "Estimated",
    EstimateStatus.DESCRIPTIVE_ONLY: "Descriptive only",
    EstimateStatus.NOT_ESTIMABLE_NO_VARIATION: "Not estimable — no variation",
    EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS: "Insufficient paired observations",
    EstimateStatus.INCOMPLETE_FOR_METRIC: "Incomplete for this metric",
}


def status_label(status: EstimateStatus) -> str:
    return _STATUS_LABELS[status]


def _traceability_filter_values(
    dataset: ValidatedDataset,
    selection: AnalysisSelection,
) -> tuple[list[str], list[str], list[str]]:
    source_names = {
        source.source_id: source.display_name
        for source in dataset.sources
        if source.source_id in selection.source_ids
    }
    rater_names = {
        rater.rater_id: rater.display_name
        for rater in dataset.raters
        if rater.rater_id in selection.rater_ids
    }
    return (
        list(source_names.values()),
        list(selection.categories),
        list(rater_names.values()),
    )


def _format_estimate(metric: MetricResult, digits: int = 3) -> str:
    if metric.value is None:
        return status_label(metric.status)
    return f"{metric.value:.{digits}f}"


def _format_percent(metric: MetricResult) -> str:
    if metric.value is None:
        return status_label(metric.status)
    return f"{metric.value * 100:.1f}%"


def _format_ci(metric: MetricResult) -> str:
    if metric.ci_low is None or metric.ci_high is None:
        return "—"
    return f"[{metric.ci_low:.3f}, {metric.ci_high:.3f}]"


def _format_p(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 0.001:
        return "< .001"
    return f"{value:.3f}"


def _format_exact_p(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.6f}"


def default_reference_rater_id(dataset: ValidatedDataset) -> str | None:
    return _default_reference_rater_id(dataset)


_CORRECTION_OPTIONS = {
    "None": "none",
    "Holm (recommended)": "holm",
    "Benjamini-Hochberg": "benjamini-hochberg",
}


def correction_options() -> tuple[str, ...]:
    return tuple(_CORRECTION_OPTIONS)


def _correction_display(value: str) -> str:
    return {
        "none": "None",
        "holm": "Holm",
        "benjamini-hochberg": "Benjamini-Hochberg",
    }.get(value, value)


_CATEGORY_ASSOCIATION_OPTIONS = {
    "Exclude categories with fewer than 5 occurrences": 5,
    "Include all grammatical categories": 1,
}


def category_association_inclusion_options() -> tuple[str, ...]:
    return tuple(_CATEGORY_ASSOCIATION_OPTIONS)


def category_association_records(analysis, dataset: ValidatedDataset) -> list[dict[str, object]]:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for result in analysis.raters:
        metaphor_count = sum(row.metaphor_count for row in result.rows)
        observed = sum(
            row.metaphor_count + row.non_metaphor_count for row in result.rows
        )
        metaphor_percent = "—" if observed == 0 else f"{100 * metaphor_count / observed:.1f}%"
        if result.adjusted_p_value is None:
            interpretation = status_label(result.status)
        elif result.adjusted_p_value < 0.05:
            interpretation = "Evidence of association at α = .05"
        else:
            interpretation = "No evidence of association at α = .05"
        rows.append(
            {
                "Rater": names.get(result.rater_id, result.rater_id),
                "Categories": sum(
                    (row.metaphor_count + row.non_metaphor_count) > 0 for row in result.rows
                ),
                "Effective N": result.effective_n,
                "Metaphor %": metaphor_percent,
                "Exact p-value": _format_exact_p(result.p_value),
                "Adjusted p-value": _format_exact_p(result.adjusted_p_value),
                "Correction": _correction_display(analysis.correction),
                "Interpretation": interpretation,
            }
        )
    return rows


def category_association_contingency_records(result) -> list[dict[str, object]]:
    return [
        {
            "Category": row.category,
            "Occurrences": row.occurrence_count,
            "Metaphor": row.metaphor_count,
            "Non-metaphor": row.non_metaphor_count,
            "Missing": row.missing_count,
        }
        for row in result.rows
    ]


def posthoc_tendency_records(
    bundle: AnalysisBundle,
    dataset: ValidatedDataset,
) -> list[dict[str, object]]:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for result in bundle.posthoc_tendency:
        rows.append(
            {
                "Rater pair": (
                    f"{names.get(result.rater_a_id, result.rater_a_id)} × "
                    f"{names.get(result.rater_b_id, result.rater_b_id)}"
                ),
                "Effective N": result.effective_n,
                "Statistic": "—" if result.statistic is None else f"{result.statistic:.3f}",
                "Raw p-value": _format_p(result.p_value),
                "Adjusted p-value": _format_p(result.adjusted_p_value),
                "Correction": _correction_display(bundle.config.multiple_testing_correction),
                "Status": status_label(result.status),
            }
        )
    return rows


def expert_benchmark_records(
    bundle: AnalysisBundle,
    dataset: ValidatedDataset,
) -> list[dict[str, object]]:
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for item in bundle.expert_benchmark:
        rows.append(
            {
                "Expert benchmark": names.get(item.benchmark_rater_id, item.benchmark_rater_id),
                "Compared rater": names.get(item.rater_id, item.rater_id),
                "Effective N": item.effective_n,
                "Agreement with expert": _format_percent(item.agreement_with_expert),
                "Sensitivity": _format_percent(item.sensitivity),
                "Specificity": _format_percent(item.specificity),
                "Precision": _format_percent(item.precision),
                "Recall": _format_percent(item.recall),
                "Confusion (TP / TN / FP / FN)": (
                    f"{item.true_positive} / {item.true_negative} / "
                    f"{item.false_positive} / {item.false_negative}"
                ),
            }
        )
    return rows


def pairwise_statistics_records(
    bundle: AnalysisBundle,
    dataset: ValidatedDataset,
) -> list[dict[str, object]]:
    rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for result in bundle.pairwise:
        rows.append(
            {
                "Rater pair": (
                    f"{rater_names.get(result.rater_a_id, result.rater_a_id)} × "
                    f"{rater_names.get(result.rater_b_id, result.rater_b_id)}"
                ),
                "Effective N": result.kappa.effective_n,
                "Raw agreement": _format_percent(result.raw_agreement),
                "Cohen's κ": _format_estimate(result.kappa),
                "95% CI": _format_ci(result.kappa),
                "Status": status_label(result.kappa.status),
            }
        )
    return rows


def group_statistics_records(
    groups: Iterable[GroupResult],
    dataset: ValidatedDataset,
) -> list[dict[str, object]]:
    rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows: list[dict[str, object]] = []
    for group in groups:
        for pair in group.pairwise:
            q = group.cochran_q
            rows.append(
                {
                    "Group": group.display_name,
                    "Lexical units": group.lexical_unit_count,
                    "Rater pair": (
                        f"{rater_names.get(pair.rater_a_id, pair.rater_a_id)} × "
                        f"{rater_names.get(pair.rater_b_id, pair.rater_b_id)}"
                    ),
                    "Raw agreement": _format_percent(pair.raw_agreement),
                    "Cohen's κ": _format_estimate(pair.kappa),
                    "Fleiss' κ": "—" if group.fleiss_kappa is None else _format_estimate(group.fleiss_kappa),
                    "Cochran's Q": "—" if q is None or q.q is None else f"{q.q:.3f}",
                    "Q df": "—" if q is None or q.degrees_of_freedom is None else q.degrees_of_freedom,
                    "Q p": "—" if q is None else _format_p(q.p_value),
                    "Kappa status": status_label(pair.kappa.status),
                    "Q status": "—" if q is None else status_label(q.status),
                }
            )
    return rows


def _render_explanation_keys(keys: tuple[str, ...]) -> None:
    import streamlit as st

    if not keys:
        return
    for key in keys:
        st.caption(explanation_text(key))


def _render_overall(bundle: AnalysisBundle, dataset: ValidatedDataset) -> None:
    import pandas as pd
    import streamlit as st

    st.markdown("#### Overall validated dataset")
    counts = bundle.counts
    pair = bundle.pairwise[0] if len(bundle.pairwise) == 1 else None
    cols = st.columns(4)
    cols[0].metric("Lexical units", counts.lexical_units)
    cols[1].metric("Raters", counts.raters)
    if pair is not None:
        cols[2].metric("Raw agreement", _format_percent(pair.raw_agreement))
        cols[3].metric("Cohen's κ", _format_estimate(pair.kappa))
    else:
        cols[2].metric("Pairwise comparisons", len(bundle.pairwise))
        cols[3].metric("Missing ratings", counts.missing_ratings)

    st.caption(
        f"{counts.metaphor_ratings} metaphor ratings · "
        f"{counts.non_metaphor_ratings} non-metaphor ratings · "
        f"{counts.missing_ratings} missing ratings"
    )

    pairwise = pairwise_statistics_records(bundle, dataset)
    if pairwise:
        st.markdown("##### Pairwise agreement")
        st.caption(
            "Raw agreement is shown before Cohen's Kappa. Kappa corrects observed agreement for "
            "agreement expected by chance and is calculated pairwise only."
        )
        st.dataframe(pd.DataFrame(pairwise), use_container_width=True, hide_index=True)


def _render_tendency(bundle: AnalysisBundle, dataset: ValidatedDataset) -> None:
    import streamlit as st

    st.markdown("#### Rater classification tendency")
    st.caption(
        "Cochran's Q is not an agreement coefficient. It tests whether raters differ systematically "
        "in how often they classify lexical units as metaphorical."
    )
    q = bundle.cochran_q
    if q is None:
        st.info("Cochran's Q requires at least two selected raters.")
        return
    cols = st.columns(4)
    cols[0].metric("Cochran's Q", "—" if q.q is None else f"{q.q:.3f}")
    cols[1].metric("df", "—" if q.degrees_of_freedom is None else q.degrees_of_freedom)
    cols[2].metric("p-value", _format_p(q.p_value))
    cols[3].metric("Effective N", q.effective_n)
    if q.status != EstimateStatus.OK:
        st.info(status_label(q.status))
    _render_explanation_keys(q.explanation_keys)
    if bundle.posthoc_tendency:
        import pandas as pd

        with st.expander("Pairwise tendency comparisons", icon=":material/compare_arrows:"):
            st.caption(
                "These McNemar comparisons examine which rater pairs differ in their binary classification "
                "tendency. Adjusted p-values use the selected multiple-comparison correction."
            )
            st.dataframe(
                pd.DataFrame(posthoc_tendency_records(bundle, dataset)),
                use_container_width=True,
                hide_index=True,
            )


def _render_specific_agreement(bundle: AnalysisBundle, dataset: ValidatedDataset) -> None:
    import pandas as pd
    import streamlit as st

    if not bundle.specific_agreement:
        return
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    rows = []
    for item in bundle.specific_agreement:
        rows.append(
            {
                "Rater pair": (
                    f"{names.get(item.rater_a_id, item.rater_a_id)} × "
                    f"{names.get(item.rater_b_id, item.rater_b_id)}"
                ),
                "Metaphor agreement": _format_percent(item.metaphor_agreement),
                "Non-metaphor agreement": _format_percent(item.non_metaphor_agreement),
            }
        )
    st.markdown("#### Class-specific agreement")
    st.caption(
        "These values show agreement separately for metaphor and non-metaphor decisions. This can "
        "reveal asymmetric difficulty that a single Kappa value may hide."
    )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_expert_benchmark(bundle: AnalysisBundle, dataset: ValidatedDataset) -> None:
    import pandas as pd
    import streamlit as st

    if not bundle.expert_benchmark:
        return
    reference_id = bundle.config.reference_rater_id or ""
    names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    reference_name = names.get(reference_id, reference_id)
    st.markdown("#### Agreement with expert benchmark")
    st.caption(
        f"{reference_name} is treated as the expert benchmark for this view. Sensitivity, specificity, "
        "precision and recall are therefore directional measures relative to that benchmark; the original "
        "annotations remain unchanged."
    )
    st.dataframe(
        pd.DataFrame(expert_benchmark_records(bundle, dataset)),
        use_container_width=True,
        hide_index=True,
    )


def _analysis_config_controls(
    dataset: ValidatedDataset,
    selection: AnalysisSelection,
) -> AnalysisConfig:
    import streamlit as st

    labels = {
        "No reference": AnalysisPerspective.NO_REFERENCE,
        "Reference rater": AnalysisPerspective.REFERENCE_RATER,
        "Expert benchmark": AnalysisPerspective.EXPERT_BENCHMARK,
    }
    default_reference = default_reference_rater_id(dataset)
    if default_reference not in selection.rater_ids:
        default_reference = None
    default_mode_index = 1 if default_reference is not None else 0
    st.markdown("#### Analysis perspective")
    st.caption(
        "Choose whether all raters should be treated symmetrically, one rater should be highlighted as the "
        "comparison focus, or one rater should be used explicitly as the expert benchmark."
    )
    selected_label = st.radio(
        "Perspective",
        tuple(labels),
        index=default_mode_index,
        horizontal=True,
        key="phase3_analysis_perspective",
    )
    perspective = labels[selected_label]
    reference_id: str | None = None
    if perspective != AnalysisPerspective.NO_REFERENCE:
        names = {rater.rater_id: rater.display_name for rater in dataset.raters}
        rater_ids = selection.rater_ids
        default_index = rater_ids.index(default_reference) if default_reference in rater_ids else 0
        selector_label = (
            "Reference rater"
            if perspective == AnalysisPerspective.REFERENCE_RATER
            else "Expert benchmark rater"
        )
        reference_id = st.selectbox(
            selector_label,
            rater_ids,
            index=default_index,
            format_func=lambda rater_id: names[rater_id],
            key="phase3_reference_rater",
        )
        if perspective == AnalysisPerspective.REFERENCE_RATER:
            st.info(
                "Reference-rater mode changes presentation order and review focus only. It does not assume "
                "that the selected rater is correct."
            )
        else:
            st.info(
                "Expert-benchmark mode treats the selected expert as the benchmark only for directional "
                "performance measures. Pairwise agreement and multi-rater statistics remain available."
            )

    correction_label = st.selectbox(
        "Multiple-comparison correction",
        correction_options(),
        index=1,
        key="phase4_multiple_correction",
        help=(
            "This correction is applied to pairwise McNemar post-hoc tests and to the per-rater "
            "grammatical-category association tests. Holm is the recommended default for confirmatory comparisons."
        ),
    )
    return AnalysisConfig(
        selected_source_ids=selection.source_ids,
        selected_categories=selection.categories,
        selected_rater_ids=selection.rater_ids,
        analysis_perspective=perspective,
        reference_rater_id=reference_id,
        multiple_testing_correction=_CORRECTION_OPTIONS[correction_label],
    )


def _render_multirater(bundle: AnalysisBundle) -> None:
    import streamlit as st

    if not bundle.overall_multirater:
        return
    st.markdown("#### Overall multi-rater agreement")
    cols = st.columns(len(bundle.overall_multirater))
    for column, metric in zip(cols, bundle.overall_multirater, strict=True):
        label = {
            "fleiss_kappa": "Fleiss' κ",
            "krippendorff_alpha": "Krippendorff's α",
        }.get(metric.metric, metric.metric)
        column.metric(label, _format_estimate(metric))
        column.caption(f"Effective N: {metric.effective_n} · {status_label(metric.status)}")
        for key in metric.explanation_keys:
            column.caption(explanation_text(key))


def render_statistics() -> None:
    import pandas as pd
    import streamlit as st

    from metaphor_agreement_studio.state.session import VALIDATED_DATASET_KEY
    from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
    page_header(
        "Statistical Analysis",
        "Detailed statistical results and analysis settings.",
        (
            "This page calculates statistics only from the researcher-validated dataset. Raw agreement "
            "is presented before chance-corrected measures. Cohen's Kappa compares two raters at a time; "
            "Cochran's Q instead tests whether raters differ in their metaphor-classification tendency."
        ),
    )
    dataset = st.session_state.get(VALIDATED_DATASET_KEY)
    if dataset is None:
        st.info("Complete Data Validation first.", icon=":material/lock:")
        return

    st.markdown("#### Analysis scope")
    selection = render_analysis_filters(dataset, "statistics")
    if len(selection.rater_ids) < 2 or not selection.source_ids or not selection.categories:
        st.info("Select at least two raters, one source and one grammatical category to run statistical analysis.")
        return
    config = _analysis_config_controls(dataset, selection)
    cache = st.session_state.get("phase3_analysis_cache")
    cache_key = (dataset.dataset_id, config)
    if cache is not None and cache[0] == cache_key:
        bundle = cache[1]
    else:
        with st.spinner("Calculating validated agreement statistics..."):
            bundle = analyze_dataset_cached(dataset, config)
        st.session_state["phase3_analysis_cache"] = (cache_key, bundle)

    for warning_key in bundle.warnings:
        st.warning(explanation_text(warning_key), icon=":material/info:")

    from metaphor_agreement_studio.ui.pages.agreement import (
        build_pairwise_kappa_figure,
        build_rater_tendency_figure,
        rater_tendency_records,
    )

    st.markdown("#### Visual summary")
    visual_left, visual_right = st.columns(2, gap="large")
    with visual_left:
        st.plotly_chart(
            build_pairwise_kappa_figure(bundle, dataset),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with visual_right:
        st.plotly_chart(
            build_rater_tendency_figure(rater_tendency_records(dataset, selection)),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    _render_overall(bundle, dataset)
    _render_tendency(bundle, dataset)
    _render_specific_agreement(bundle, dataset)
    _render_expert_benchmark(bundle, dataset)
    _render_multirater(bundle)

    st.markdown("#### By grammatical category")
    st.caption(
        "Each grammatical category is analysed independently. One-item or no-variation subsets are "
        "reported explicitly instead of displaying NaN."
    )
    category_rows = group_statistics_records(bundle.by_category, dataset)
    st.dataframe(pd.DataFrame(category_rows), use_container_width=True, hide_index=True)

    st.markdown("#### By source group")
    st.caption(
        "Primary sources are analysed separately. Aggregate sources remain available as explicit source "
        "views but are excluded from the default overall count to prevent double counting."
    )
    source_rows = group_statistics_records(bundle.by_source, dataset)
    st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Grammatical Category Association")
    st.caption(
        "Fisher-Freeman-Halton exact tests evaluate whether metaphor classification is associated "
        "with grammatical category within each rater. This tests association, not inter-rater agreement. "
        "Excluding categories with fewer than 5 occurrences is an optional researcher rule, not a "
        "mathematical requirement of the exact test."
    )
    inclusion_label = st.radio(
        "Category inclusion",
        category_association_inclusion_options(),
        index=0,
        horizontal=True,
        key="statistics_category_association_inclusion",
        help=(
            "Choose whether low-frequency grammatical categories are excluded from this exact-test block. "
            "The choice is recorded in the analysis configuration and PDF report."
        ),
    )
    association_config = replace(
        config,
        category_association_min_occurrences=_CATEGORY_ASSOCIATION_OPTIONS[inclusion_label],
    )
    from metaphor_agreement_studio.statistics.category_association import (
        analyze_grammatical_category_association,
    )

    with st.spinner("Calculating exact grammatical-category association tests..."):
        category_association = analyze_grammatical_category_association(
            dataset, association_config
        )
    bundle_for_report = replace(bundle, config=association_config)
    persist_analysis_if_project(st.session_state, association_config)

    included_text = ", ".join(
        f"{category} (n={count})" for category, count in category_association.included_categories
    ) or "None"
    excluded_text = ", ".join(
        f"{category} (n={count})" for category, count in category_association.excluded_categories
    ) or "None"
    st.caption(f"Included categories: {included_text}")
    st.caption(f"Excluded by the selected rule: {excluded_text}")
    st.dataframe(
        pd.DataFrame(category_association_records(category_association, dataset)),
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Contingency tables and category counts", icon=":material/table_chart:"):
        rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
        for result in category_association.raters:
            st.markdown(f"**{rater_names.get(result.rater_id, result.rater_id)}**")
            st.dataframe(
                pd.DataFrame(category_association_contingency_records(result)),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("#### Comparison report")
    st.caption(
        "Choose which raters should appear in the report. The report is recalculated using only the raters selected here, "
        "while keeping the current source, grammatical-category and statistical settings."
    )
    report_rater_names = {rater.rater_id: rater.display_name for rater in dataset.raters}
    report_rater_ids = tuple(
        st.multiselect(
            "Raters included in report",
            tuple(report_rater_names),
            default=selection.rater_ids,
            format_func=lambda rater_id: report_rater_names[rater_id],
            key="statistics_report_raters",
            help=(
                "The PDF is recalculated from the validated annotations using only these raters. "
                "Changing this selection does not alter the source workbook."
            ),
        )
    )
    report_problem = None
    if len(report_rater_ids) < 2:
        report_problem = "Select at least two raters to generate an agreement report."
    elif (
        association_config.analysis_perspective != AnalysisPerspective.NO_REFERENCE
        and association_config.reference_rater_id not in report_rater_ids
    ):
        reference_name = report_rater_names.get(
            association_config.reference_rater_id or "",
            association_config.reference_rater_id or "reference rater",
        )
        report_problem = (
            f"Include the current reference rater ({reference_name}) in the report, or change the analysis perspective."
        )

    if report_problem is not None:
        st.info(report_problem, icon=":material/info:")
    else:
        report_config = build_report_analysis_config(association_config, report_rater_ids)
        if report_config == association_config:
            report_bundle = bundle_for_report
            report_category_association = category_association
        else:
            with st.spinner("Recalculating the selected report scope..."):
                report_bundle = analyze_dataset_cached(dataset, report_config)
                report_category_association = analyze_grammatical_category_association(
                    dataset, report_config
                )
        report_key = (
            dataset.dataset_id,
            report_config,
            st.session_state.get(PROJECT_NAME_KEY),
            st.session_state.get(DATASET_VERSION_KEY),
            st.session_state.get(ANALYSIS_VERSION_KEY),
        )
        report_cache = st.session_state.get("comparison_report_pdf_cache")
        if report_cache is None or report_cache[0] != report_key:
            with st.spinner("Preparing the comparison report PDF..."):
                report_filename, report_payload = build_comparison_report_download(
                    dataset,
                    report_bundle,
                    st.session_state,
                    category_association=report_category_association,
                )
            st.session_state["comparison_report_pdf_cache"] = (
                report_key, report_filename, report_payload
            )
        else:
            _, report_filename, report_payload = report_cache
        selected_names = ", ".join(report_rater_names[rater_id] for rater_id in report_rater_ids)
        st.caption(f"Report scope: {selected_names}")
        st.download_button(
            "Generate Comparison Report (PDF)",
            data=report_payload,
            file_name=report_filename,
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            key="statistics_download_comparison_report",
            help=(
                "Includes analysis design, overall agreement, classification tendency, grammatical-category "
                "association, category/source comparisons, disagreement cases and reproducibility hashes."
            ),
        )

    st.markdown("#### Traceability")
    st.caption(
        "Open the exact validated annotation matrix behind this analytical scope. The source workbook remains unchanged."
    )
    if st.button(
        "View validated annotations",
        icon=":material/table_view:",
        key="statistics_open_annotations",
    ):
        from metaphor_agreement_studio.state.session import set_route
        from metaphor_agreement_studio.ui.navigation import Route

        source_values, category_values, rater_values = _traceability_filter_values(
            dataset, selection
        )
        st.session_state["annotations_source_filter"] = source_values
        st.session_state["annotations_category_filter"] = category_values
        st.session_state["annotations_rater_filter"] = rater_values
        set_route(Route.ANNOTATIONS)
        st.rerun()

    with st.expander("Statistical engine notes", icon=":material/functions:"):
        st.markdown(
            "- Missing ratings are never converted to non-metaphor.\n"
            "- Every pairwise result reports its effective N.\n"
            "- Perfect observed agreement can coexist with a non-estimable Kappa when there is no "
            "class variation.\n"
            "- Agreement, Review, Categories, Source Groups and Rater Explorer provide guided visual workspaces; this page remains the advanced statistical view."
        )
