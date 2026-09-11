from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import tempfile
from pathlib import Path

from metaphor_agreement_studio.figures.data import (
    build_agreement_fingerprint_data,
    build_agreement_vs_sample_size_data,
    build_category_agreement_data,
    build_disagreement_by_category_data,
    build_metaphor_rate_by_rater_data,
    build_multi_rater_patterns_data,
    build_pairwise_kappa_matrix_data,
    build_rater_divergence_data,
    build_review_density_data,
    build_source_comparison_data,
    build_specific_agreement_data,
    sort_fingerprint_data,
)
from metaphor_agreement_studio.figures.interactive import render_interactive_figure
from metaphor_agreement_studio import __version__
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureProvenance, FigureSpec
from metaphor_agreement_studio.common.cache_keys import analysis_config_hash, dataset_content_hash
from metaphor_agreement_studio.statistics.engine import analyze_dataset_cached
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.state.session import PROJECT_CONTEXT_KEY, PROJECT_NAME_KEY, WORKSPACE_MODE_KEY, set_project_context


@dataclass(frozen=True, slots=True)
class FigureGalleryItem:
    kind: FigureKind
    label: str
    description: str



PUBLICATION_EXPORT_FORMATS = ("PDF", "SVG", "PNG")
PUBLICATION_SIZE_OPTIONS = ("single-column", "double-column", "presentation")
FINGERPRINT_SORT_OPTIONS = ("Source order", "Grammatical category", "Most disagreement first")

FIGURE_GALLERY = (
    FigureGalleryItem(FigureKind.AGREEMENT_FINGERPRINT, "Annotation Agreement Map", "Lexical occurrences × raters."),
    FigureGalleryItem(FigureKind.PAIRWISE_KAPPA_MATRIX, "Pairwise Kappa Matrix", "Pairwise chance-corrected agreement."),
    FigureGalleryItem(FigureKind.AGREEMENT_BY_CATEGORY, "Agreement by Grammatical Category", "Kappa estimates by part of speech."),
    FigureGalleryItem(FigureKind.AGREEMENT_VS_SAMPLE_SIZE, "Agreement vs Sample Size", "Agreement interpreted alongside N."),
    FigureGalleryItem(FigureKind.METAPHOR_RATE_BY_RATER, "Metaphor Classification Rates", "Classification tendency, not agreement."),
    FigureGalleryItem(FigureKind.DISAGREEMENT_BY_CATEGORY, "Disagreement by Grammatical Category", "Where disagreement cases concentrate."),
    FigureGalleryItem(FigureKind.RATER_DIVERGENCE, "Rater Divergence Profile", "Mean pairwise Kappa by rater."),
    FigureGalleryItem(FigureKind.MULTI_RATER_PATTERNS, "Multi-rater Patterns", "Exact combinations of metaphor decisions."),
    FigureGalleryItem(FigureKind.SOURCE_COMPARISON, "Source Comparison", "Agreement estimates across source groups."),
    FigureGalleryItem(FigureKind.SPECIFIC_AGREEMENT, "Specific Agreement", "Metaphor and non-metaphor agreement separately."),
    FigureGalleryItem(FigureKind.REVIEW_DENSITY, "Disagreement Density Map", "Source × category concentration of disagreements."),
)


def _default_pair(bundle) -> tuple[str, str] | None:
    if bundle.pairwise:
        pair = bundle.pairwise[0]
        return pair.rater_a_id, pair.rater_b_id
    return None


def _figure_data(kind: FigureKind, dataset, bundle, rater_pair) -> FigureDataset:
    if kind is FigureKind.AGREEMENT_FINGERPRINT:
        return build_agreement_fingerprint_data(dataset, bundle)
    if kind is FigureKind.PAIRWISE_KAPPA_MATRIX:
        return build_pairwise_kappa_matrix_data(bundle, dataset)
    if kind is FigureKind.AGREEMENT_BY_CATEGORY:
        return build_category_agreement_data(bundle, rater_pair)
    if kind is FigureKind.AGREEMENT_VS_SAMPLE_SIZE:
        return build_agreement_vs_sample_size_data(bundle, rater_pair)
    if kind is FigureKind.METAPHOR_RATE_BY_RATER:
        return build_metaphor_rate_by_rater_data(dataset, bundle)
    if kind is FigureKind.DISAGREEMENT_BY_CATEGORY:
        return build_disagreement_by_category_data(dataset, bundle)
    if kind is FigureKind.RATER_DIVERGENCE:
        return build_rater_divergence_data(bundle, dataset)
    if kind is FigureKind.MULTI_RATER_PATTERNS:
        return build_multi_rater_patterns_data(dataset, bundle)
    if kind is FigureKind.SOURCE_COMPARISON:
        return build_source_comparison_data(bundle, rater_pair)
    if kind is FigureKind.SPECIFIC_AGREEMENT:
        return build_specific_agreement_data(bundle, dataset)
    if kind is FigureKind.REVIEW_DENSITY:
        return build_review_density_data(dataset, bundle)
    raise ValueError(kind)


def _analysis_bundle(state, dataset):
    cache = state.get("phase3_analysis_cache")
    if isinstance(cache, tuple) and len(cache) == 2:
        return cache[1]
    config = AnalysisConfig(selected_rater_ids=tuple(r.rater_id for r in dataset.raters))
    bundle = analyze_dataset_cached(dataset, config)
    state["phase3_analysis_cache"] = ((dataset.dataset_id, config), bundle)
    return bundle


def _provenance(state, dataset, bundle, pair) -> FigureProvenance:
    context = state.get(PROJECT_CONTEXT_KEY)
    project_name = str(state.get(PROJECT_NAME_KEY, "Quick Analysis"))
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
    names = tuple(rater.display_name for rater in dataset.raters)
    filters = {
        "selected_source_ids": list(bundle.config.selected_source_ids),
        "selected_categories": list(bundle.config.selected_categories),
        "selected_rater_ids": list(bundle.config.selected_rater_ids),
        "rater_pair": list(pair) if pair else [],
    }
    return FigureProvenance(
        project_name=project_name,
        dataset_version=dataset_version,
        analysis_version=analysis_version,
        raters=names,
        filters=filters,
        software_version=__version__,
        generated_at=datetime.now(timezone.utc).isoformat(),
        dataset_content_hash=dataset_content_hash(dataset),
        analysis_config_hash=analysis_config_hash(bundle.config),
    )


def _render_artifact_freshness(state) -> None:
    import streamlit as st

    context = state.get(PROJECT_CONTEXT_KEY)
    if context is None or not getattr(context, "artifacts", ()):
        return
    from metaphor_agreement_studio.persistence.versioning import artifact_is_current

    figure_artifacts = [a for a in context.artifacts if a.kind == "figure"]
    if not figure_artifacts:
        return
    with st.expander("Project figure history", icon=":material/history:"):
        for artifact in figure_artifacts[:12]:
            current = artifact_is_current(
                artifact, context.current_dataset_version, context.current_analysis_version
            )
            label = artifact.metadata.get("title", Path(artifact.stored_relpath).name)
            status = "Up to date" if current else "Dataset/analysis changed — regenerate"
            st.write(f"**{label}** · {status}")


def render_figures() -> None:
    import streamlit as st

    page_header(
        "Figures",
        "Interactive exploration and publication-ready scientific graphics.",
        "Every figure is built from the validated analytical data, not from formatted dashboard text.",
    )
    dataset = st.session_state.get("validated_dataset")
    if dataset is None:
        st.info("Complete data validation first.", icon=":material/lock:")
        return
    bundle = _analysis_bundle(st.session_state, dataset)
    labels = [item.label for item in FIGURE_GALLERY]
    selected_label = st.selectbox("Figure", labels, key="phase6_figure_kind")
    item = next(item for item in FIGURE_GALLERY if item.label == selected_label)
    st.caption(item.description)
    mode = st.segmented_control("View", ["Interactive", "Publication"], default="Interactive")
    pair = _default_pair(bundle)
    if item.kind in {
        FigureKind.AGREEMENT_BY_CATEGORY,
        FigureKind.AGREEMENT_VS_SAMPLE_SIZE,
        FigureKind.SOURCE_COMPARISON,
    } and pair is None:
        st.info("This figure needs at least two selected raters.")
        return
    data = _figure_data(item.kind, dataset, bundle, pair)
    if item.kind is FigureKind.AGREEMENT_FINGERPRINT:
        sort_mode = st.selectbox("Sort lexical occurrences", FINGERPRINT_SORT_OPTIONS)
        data = FigureDataset(data.kind, sort_fingerprint_data(data.frame, sort_mode), data.metadata)

    if mode == "Publication":
        from metaphor_agreement_studio.export.package import safe_filename
        from metaphor_agreement_studio.figures.publication import (
            render_publication_figure,
            save_publication_figure,
        )

        control_cols = st.columns(4)
        size = control_cols[0].selectbox("Size", PUBLICATION_SIZE_OPTIONS, index=1)
        fmt = control_cols[1].selectbox("Format", PUBLICATION_EXPORT_FORMATS)
        dpi = control_cols[2].selectbox("PNG resolution", (300, 600), disabled=fmt != "PNG")
        background = control_cols[3].selectbox("Background", ("White", "Transparent"))
        spec = FigureSpec(item.kind, item.label, rater_pair=pair, size_preset=size)
        fig = render_publication_figure(spec, data)
        st.pyplot(fig, use_container_width=False)
        st.caption(
            "Publication view removes dashboard chrome and remains interpretable without color alone."
        )
        if st.button("Prepare figure export", icon=":material/download:"):
            extension = fmt.lower()
            stem = safe_filename(item.label.lower().replace(" ", "_"))
            provenance = _provenance(st.session_state, dataset, bundle, pair)
            with tempfile.TemporaryDirectory(prefix="mas-figure-") as temp:
                target = Path(temp) / f"{stem}.{extension}"
                save_publication_figure(
                    fig,
                    target,
                    extension,
                    dpi=dpi,
                    provenance=provenance,
                    transparent=background == "Transparent",
                )
                sidecar = target.with_name(f"{target.stem}.provenance.json")
                figure_bytes = target.read_bytes()
                provenance_bytes = sidecar.read_bytes()
                context = st.session_state.get(PROJECT_CONTEXT_KEY)
                if (
                    st.session_state.get(WORKSPACE_MODE_KEY) == "research_project"
                    and context is not None
                ):
                    from metaphor_agreement_studio.persistence.project_service import register_artifact

                    updated = register_artifact(
                        context,
                        target,
                        "figure",
                        {"title": item.label, "format": extension, "size": size},
                    )
                    updated = register_artifact(
                        updated,
                        sidecar,
                        "figure_provenance",
                        {"title": item.label},
                    )
                    set_project_context(updated, st.session_state)
            mime = {"pdf": "application/pdf", "svg": "image/svg+xml", "png": "image/png"}[extension]
            st.download_button(
                f"Download {fmt}",
                figure_bytes,
                file_name=f"{stem}.{extension}",
                mime=mime,
            )
            st.download_button(
                "Download provenance JSON",
                provenance_bytes,
                file_name=f"{stem}.provenance.json",
                mime="application/json",
            )
    else:
        spec = FigureSpec(item.kind, item.label, rater_pair=pair)
        fig = render_interactive_figure(spec, data)
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    with st.expander("Figure data", icon=":material/table_view:"):
        st.dataframe(data.frame, use_container_width=True, hide_index=True)
    _render_artifact_freshness(st.session_state)
