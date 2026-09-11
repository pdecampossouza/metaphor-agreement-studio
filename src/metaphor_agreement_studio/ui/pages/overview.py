from __future__ import annotations

import html
from pathlib import Path

from metaphor_agreement_studio.config import default_scan_roots
from metaphor_agreement_studio.import_engine.discovery import discover_workbooks
from metaphor_agreement_studio.state.session import set_route
from metaphor_agreement_studio.ui.components import page_header, semantic_legend
from metaphor_agreement_studio.ui.navigation import Route


def overview_candidates(base_dir: Path):
    return discover_workbooks(default_scan_roots(base_dir))


def _stat_grid(candidate_count: int) -> str:
    return f"""
    <div class="mas-stat-grid">
      <div class="mas-stat">
        <div class="mas-stat-label">Local candidates</div>
        <div class="mas-stat-value">{candidate_count}</div>
        <div class="mas-stat-note">Workbook files detected, not imported</div>
      </div>
      <div class="mas-stat">
        <div class="mas-stat-label">Workspace mode</div>
        <div class="mas-stat-value" style="font-size:1.05rem">Quick Analysis</div>
        <div class="mas-stat-note">Temporary until you save a research project</div>
      </div>
      <div class="mas-stat">
        <div class="mas-stat-label">Validation</div>
        <div class="mas-stat-value" style="font-size:1.05rem">Pending</div>
        <div class="mas-stat-note">Analysis waits for human validation</div>
      </div>
      <div class="mas-stat">
        <div class="mas-stat-label">Source changes</div>
        <div class="mas-stat-value">0</div>
        <div class="mas-stat-note">Original workbooks are never modified</div>
      </div>
    </div>
    """


def render_overview(base_dir: Path) -> None:
    import streamlit as st

    candidates = overview_candidates(base_dir)
    page_header(
        "Overview",
        "A traceable starting point for lexical metaphor annotation studies.",
        (
            "This page shows local workbook candidates before any analytical data are created. "
            "Detection only identifies files; it does not yet inspect worksheets, decode colors, "
            "or calculate agreement statistics."
        ),
    )
    semantic_legend()
    st.markdown(_stat_grid(len(candidates)), unsafe_allow_html=True)

    st.markdown("#### Source workbooks")
    if not candidates:
        st.markdown(
            """
            <div class="mas-card">
              <div class="mas-card-eyebrow">Local discovery</div>
              <div class="mas-card-title">No workbook detected yet</div>
              <div class="mas-card-copy">
                Place an Excel workbook in this folder or in the <code>imports</code> folder.
                Supported files are <code>.xlsx</code> and <code>.xlsm</code>.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for index, candidate in enumerate(candidates):
        safe_name = html.escape(candidate.display_name)
        st.markdown(
            f"""
            <div class="mas-card">
              <div class="mas-card-eyebrow">Source workbook detected</div>
              <div class="mas-card-title">{safe_name}</div>
              <div class="mas-card-copy">
                Found locally. Nothing has been imported into the validated dataset yet.<br>
                Inspect the workbook structure and confirm how annotations are encoded before analysis.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Inspect & Validate",
            key=f"inspect_candidate_{index}",
            type="primary",
            icon=":material/fact_check:",
        ):
            st.session_state["selected_workbook_path"] = str(candidate.path)
            set_route(Route.DATA_VALIDATION)
            st.rerun()
        st.write("")
