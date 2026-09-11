from __future__ import annotations

import tempfile
from pathlib import Path

from metaphor_agreement_studio.export.package import ResearchPackageSelection, create_research_package
from metaphor_agreement_studio.state.session import (
    PRIMARY_WORKBOOK_KEY,
    PROJECT_CONTEXT_KEY,
    PROJECT_NAME_KEY,
    WORKSPACE_MODE_KEY,
    set_project_context,
)
from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.ui.components import page_header

EXPORT_GROUPS = {
    "DATA": ("Validated annotations", "Long-format dataset"),
    "STATISTICAL RESULTS": ("Results workbook", "Overall and grouped statistics"),
    "PUBLICATION": ("Publication figures", "LaTeX tables", "Suggested reporting text"),
    "DOCUMENTATION": ("Validation summary", "Analysis settings", "Reproducibility manifest"),
}


def _package_artifact_flags(selections: dict[str, bool]) -> dict[str, bool]:
    return {
        "include_validated_xlsx": selections["Validated annotations"],
        "include_long_csv": selections["Long-format dataset"],
        "include_results_workbook": selections["Results workbook"] or selections["Overall and grouped statistics"],
        "include_publication_figures": selections["Publication figures"],
        "include_latex_tables": selections["LaTeX tables"],
        "include_reporting_text": selections["Suggested reporting text"],
        "include_validation_summary": selections["Validation summary"],
        "include_analysis_settings": selections["Analysis settings"],
    }


def _bundle(state, dataset):
    cache = state.get("phase3_analysis_cache")
    if isinstance(cache, tuple) and len(cache) == 2:
        return cache[1]
    config = AnalysisConfig(selected_rater_ids=tuple(r.rater_id for r in dataset.raters))
    bundle = analyze_dataset_cached(dataset, config)
    state["phase3_analysis_cache"] = ((dataset.dataset_id, config), bundle)
    return bundle


def _source_files(state) -> tuple[object, ...]:
    context = state.get(PROJECT_CONTEXT_KEY)
    if context is not None:
        return tuple(context.source_files)
    primary = state.get(PRIMARY_WORKBOOK_KEY)
    if primary is None:
        return ()
    if hasattr(primary, "local_path"):
        return (Path(primary.local_path),)
    try:
        return (Path(primary),)
    except TypeError:
        return ()


def render_export_center() -> None:
    import streamlit as st

    page_header(
        "Export Center",
        "Create datasets, statistical results, publication outputs, and reproducibility packages.",
        "Exports use the validated canonical dataset and never modify the original source workbook.",
    )
    dataset = st.session_state.get("validated_dataset")
    if dataset is None:
        st.info("Complete data validation first.", icon=":material/lock:")
        return
    bundle = _bundle(st.session_state, dataset)

    selections: dict[str, bool] = {}
    for group, items in EXPORT_GROUPS.items():
        st.markdown(f"#### {group}")
        for item in items:
            if item == "Reproducibility manifest":
                selections[item] = st.checkbox(
                    item,
                    value=True,
                    disabled=True,
                    help="Every research package includes a machine-readable reproducibility manifest.",
                    key=f"phase6_export_{group}_{item}",
                )
            else:
                selections[item] = st.checkbox(item, value=True, key=f"phase6_export_{group}_{item}")

    context = st.session_state.get(PROJECT_CONTEXT_KEY)
    project_name = st.session_state.get(PROJECT_NAME_KEY, "Quick Analysis")
    dataset_version = (
        context.current_dataset_version.display_id
        if context is not None and context.current_dataset_version is not None
        else "Quick Analysis"
    )
    analysis_version = (
        context.current_analysis_version.display_id
        if context is not None and context.current_analysis_version is not None
        else "Current session"
    )
    audit_events = tuple(context.audit_events) if context is not None else ()

    if st.button("Create Research Package", type="primary", icon=":material/archive:"):
        package_selection = ResearchPackageSelection(
            dataset=dataset,
            analysis_bundle=bundle,
            project_name=str(project_name),
            dataset_version=dataset_version,
            analysis_version=analysis_version,
            source_files=_source_files(st.session_state),
            audit_events=audit_events,
            include_data=False,
            include_statistics=False,
            include_publication=False,
            include_documentation=False,
            **_package_artifact_flags(selections),
        )
        with tempfile.TemporaryDirectory(prefix="mas-ui-export-") as temp:
            path = create_research_package(package_selection, Path(temp) / "Metaphor_Agreement_Research_Package.zip")
            payload = path.read_bytes()
            if st.session_state.get(WORKSPACE_MODE_KEY) == "research_project" and context is not None:
                from metaphor_agreement_studio.persistence.project_service import register_artifact

                updated = register_artifact(
                    context,
                    path,
                    "research_package",
                    {"dataset_version": dataset_version, "analysis_version": analysis_version},
                )
                set_project_context(updated, st.session_state)
        st.download_button(
            "Download Research Package",
            payload,
            file_name="Metaphor_Agreement_Research_Package.zip",
            mime="application/zip",
            icon=":material/download:",
        )
        st.caption("The package includes a reproducibility manifest and only the output groups selected above.")
