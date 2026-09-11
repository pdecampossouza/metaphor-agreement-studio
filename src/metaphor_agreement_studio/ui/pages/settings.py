from __future__ import annotations

from metaphor_agreement_studio.state.session import WORKSPACE_MODE_KEY
from metaphor_agreement_studio.ui.components import page_header


def render_settings() -> None:
    import streamlit as st

    page_header(
        "Settings",
        "Local application and reproducibility-sensitive preferences.",
        "Project data remain local. Statistical settings that affect results are versioned with analyses rather than hidden here.",
    )
    mode = st.session_state.get(WORKSPACE_MODE_KEY, "quick_analysis")
    st.markdown("### Research environment")
    st.markdown(f"**Workspace mode:** {'Research Project' if mode == 'research_project' else 'Quick Analysis'}")
    st.caption("Local-first processing · source workbooks are never overwritten.")
    st.markdown("### Cross-platform launch")
    st.caption(
        "The scientific code is identical on Windows and macOS. Only launch/stop scripts and installation helpers differ."
    )
