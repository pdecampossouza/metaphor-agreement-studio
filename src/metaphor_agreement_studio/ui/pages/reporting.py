from __future__ import annotations

from metaphor_agreement_studio.reporting.latex import render_figure_latex, render_latex_table
from metaphor_agreement_studio.reporting.text import REPORTING_WARNING, generate_method_summary, suggest_statistical_reporting
from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.ui.components import page_header


def _bundle(state, dataset):
    cache = state.get("phase3_analysis_cache")
    if isinstance(cache, tuple) and len(cache) == 2:
        return cache[1]
    config = AnalysisConfig(selected_rater_ids=tuple(r.rater_id for r in dataset.raters))
    bundle = analyze_dataset_cached(dataset, config)
    state["phase3_analysis_cache"] = ((dataset.dataset_id, config), bundle)
    return bundle


def render_reporting() -> None:
    import streamlit as st

    page_header(
        "LaTeX & Reporting",
        "Generate traceable tables, captions, and statistical reporting text.",
        "Generated prose is reporting assistance, not a substantive interpretation of metaphor theory.",
    )
    dataset = st.session_state.get("validated_dataset")
    if dataset is None:
        st.info("Complete data validation first.")
        return
    bundle = _bundle(st.session_state, dataset)
    tabs = st.tabs(["Tables", "Figures", "Suggested statistical reporting", "Analysis method summary"])
    with tabs[0]:
        table_label = st.selectbox("Table", ["Overall agreement", "Pairwise agreement", "Agreement by POS", "Agreement by source"])
        kind = {
            "Overall agreement": "overall",
            "Pairwise agreement": "pairwise",
            "Agreement by POS": "by_category",
            "Agreement by source": "by_source",
        }[table_label]
        selection = {}
        if bundle.pairwise:
            first = bundle.pairwise[0]
            selection["rater_pair"] = (first.rater_a_id, first.rater_b_id)
        latex = render_latex_table(kind, bundle, selection)
        st.code(latex, language="latex")
        st.download_button("Download .tex", latex.encode("utf-8"), file_name=f"{kind}.tex", mime="text/plain")
    with tabs[1]:
        snippet = render_figure_latex("figure_01.pdf", "Inter-rater agreement for lexical metaphor annotation.", "fig:agreement")
        st.code(snippet, language="latex")
    with tabs[2]:
        if bundle.pairwise:
            st.text_area("Suggested text", suggest_statistical_reporting(bundle.pairwise[0]), height=180)
        else:
            st.info("At least two raters are required for pairwise reporting text.")
        st.caption(REPORTING_WARNING)
    with tabs[3]:
        st.text_area("Method summary", generate_method_summary(bundle.config, bundle.counts.raters), height=220)
        st.caption(REPORTING_WARNING)
