from __future__ import annotations

from pathlib import Path

from metaphor_agreement_studio.persistence.project_service import open_project
from metaphor_agreement_studio.state.session import PROJECT_CONTEXT_KEY
from metaphor_agreement_studio.ui.components import page_header


def render_audit() -> None:
    import streamlit as st

    page_header(
        "Audit History",
        "A researcher-readable history of project and dataset changes.",
        (
            "The audit trail records meaningful research actions such as project creation, preserved source files, "
            "dataset versions, analysis versions, validation changes, and backups."
        ),
    )
    context = st.session_state.get(PROJECT_CONTEXT_KEY)
    if context is None:
        st.info("Audit History becomes persistent after you save or open a Research Project.")
        return
    try:
        context = open_project(Path(context.root))
        st.session_state[PROJECT_CONTEXT_KEY] = context
    except Exception:
        pass
    if not context.audit_events:
        st.caption("No audit events have been recorded yet.")
        return
    for event in context.audit_events:
        with st.container(border=True):
            st.markdown(f"**{event.summary}**")
            st.caption(event.occurred_at)
            tags = []
            if event.dataset_version_id:
                tags.append(f"Dataset: {event.dataset_version_id}")
            if event.analysis_id:
                tags.append(f"Analysis: {event.analysis_id}")
            if tags:
                st.caption(" · ".join(tags))
            if event.details:
                with st.expander("Details"):
                    for key, value in event.details.items():
                        st.markdown(f"**{key.replace('_', ' ').title()}**  \n{value}")
