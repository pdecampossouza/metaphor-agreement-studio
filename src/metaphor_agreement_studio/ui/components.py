from __future__ import annotations

import html


def page_header(title: str, subtitle: str, help_text: str | None = None) -> None:
    import streamlit as st

    st.markdown(
        (
            '<section class="mas-page-title">'
            f"<h1>{html.escape(title)}</h1>"
            f"<p>{html.escape(subtitle)}</p>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )
    if help_text:
        with st.expander("How to read this page", icon=":material/info:"):
            st.markdown(help_text)


def semantic_legend() -> None:
    from metaphor_agreement_studio.ui.legends import render_annotation_legend

    render_annotation_legend()


def status_pill(label: str, tone: str = "neutral") -> str:
    safe_tone = tone if tone in {"neutral", "valid", "review"} else "neutral"
    return f'<span class="mas-pill mas-status-{safe_tone}">{html.escape(label)}</span>'
