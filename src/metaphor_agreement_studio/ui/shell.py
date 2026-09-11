from __future__ import annotations

from collections.abc import Callable
import html

from metaphor_agreement_studio.config import APP_NAME, APP_SUBTITLE
from metaphor_agreement_studio.state.session import (
    ANALYSIS_VERSION_KEY,
    DATASET_STATUS_KEY,
    DATASET_VERSION_KEY,
    PROJECT_NAME_KEY,
    PROJECT_CONTEXT_KEY,
    WORKSPACE_MODE_KEY,
    current_route,
    ensure_session_state,
    set_route,
)
from metaphor_agreement_studio.ui.navigation import NAV_SECTIONS
from metaphor_agreement_studio.ui.styles import load_styles


def _render_topbar() -> None:
    import streamlit as st

    project_name = st.session_state.get(PROJECT_NAME_KEY, "Quick Analysis")
    dataset_status = st.session_state.get(DATASET_STATUS_KEY, "not_validated")
    status_label = "Validated" if dataset_status == "validated" else "Not validated"
    status_class = "valid" if dataset_status == "validated" else "review"

    st.markdown(
        f"""
        <header class="mas-topbar">
          <div class="mas-brand-lockup">
            <div class="mas-mark" aria-hidden="true">♪</div>
            <div>
              <div class="mas-brand">{html.escape(APP_NAME)}</div>
              <div class="mas-brand-subtitle">{html.escape(APP_SUBTITLE)}</div>
            </div>
          </div>
          <div class="mas-topbar-meta">
            <div>
              <span class="mas-meta-label">Workspace</span>
              <strong>{html.escape(str(project_name))}</strong>
            </div>
            <span class="mas-pill mas-status-{status_class}">{status_label}</span>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_button(item, active: bool) -> bool:
    import streamlit as st

    button_type = "primary" if active else "secondary"
    kwargs = {
        "label": item.label,
        "key": f"nav_{item.route.value}",
        "use_container_width": True,
        "type": button_type,
    }
    try:
        return st.button(icon=f":material/{item.icon}:", **kwargs)
    except TypeError:
        return st.button(**kwargs)


def _render_navigation() -> None:
    import streamlit as st

    route = current_route()
    with st.sidebar:
        st.markdown('<div class="mas-sidebar-kicker">RESEARCH WORKSPACE</div>', unsafe_allow_html=True)
        for section in NAV_SECTIONS:
            st.markdown(
                f'<div class="mas-nav-section">{html.escape(section.label)}</div>',
                unsafe_allow_html=True,
            )
            for item in section.items:
                if _sidebar_button(item, item.route == route):
                    set_route(item.route)
                    st.rerun()
        st.markdown(
            """
            <div class="mas-sidebar-note">
              <strong>Local research environment</strong><br>
              Source workbooks remain unchanged during discovery.
            </div>
            """,
            unsafe_allow_html=True,
        )


def status_strip_parts(state) -> list[str]:
    dataset_status = state.get(DATASET_STATUS_KEY, "not_validated")
    project_name = state.get(PROJECT_NAME_KEY, "Quick Analysis")
    dataset = state.get("validated_dataset")
    mode = state.get(WORKSPACE_MODE_KEY, "quick_analysis")
    context = state.get(PROJECT_CONTEXT_KEY)

    parts = ["Dataset validated" if dataset_status == "validated" else "Dataset not validated"]
    if mode == "quick_analysis" or context is None:
        parts.extend(["Quick Analysis", "Not saved"])
        if dataset_status == "validated" and dataset is not None:
            non_aggregate = {source.source_id for source in dataset.sources if not source.is_aggregate}
            analytical_units = sum(unit.source_id in non_aggregate for unit in dataset.units)
            parts.append(f"{analytical_units} analytical units")
            parts.append(f"{len(dataset.raters)} raters")
        return parts

    dataset_version = context.current_dataset_version
    analysis_version = context.current_analysis_version
    stale = bool(
        dataset_version
        and analysis_version
        and analysis_version.dataset_version_id != dataset_version.version_id
    )
    if stale:
        parts[0] = "Dataset modified"
        parts.extend(["Analysis out of date", "Re-run analysis"])
    if dataset_version:
        parts.append(dataset_version.display_id)
    if context.dataset is not None:
        non_aggregate = {source.source_id for source in context.dataset.sources if not source.is_aggregate}
        analytical_units = sum(unit.source_id in non_aggregate for unit in context.dataset.units)
        parts.append(f"{analytical_units} analytical units")
        parts.append(f"{len(context.dataset.raters)} raters")
    parts.append(str(project_name))
    if analysis_version:
        parts.append(f"Analysis {analysis_version.display_id}")
    return parts


def _render_status_strip() -> None:
    import streamlit as st

    parts = status_strip_parts(st.session_state)

    st.markdown(
        f'<div class="mas-status-strip" role="status" aria-live="polite">'
        f"{' &nbsp;·&nbsp; '.join(html.escape(part) for part in parts)}</div>",
        unsafe_allow_html=True,
    )


def render_shell(page_renderer: Callable[[], None]) -> None:
    ensure_session_state()
    load_styles()
    _render_topbar()
    _render_navigation()
    st = __import__("streamlit")
    with st.container():
        page_renderer()
    _render_status_strip()
