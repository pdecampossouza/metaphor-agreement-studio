from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegendItem:
    symbol: str
    label: str
    css_class: str


ANNOTATION_LEGEND_ITEMS = (
    LegendItem("●", "Metaphor", "mas-metaphor"),
    LegendItem("○", "Non-metaphor", "mas-non-metaphor"),
    LegendItem("–", "Missing / not rated", "mas-missing"),
    LegendItem("◆", "Requires review", "mas-review"),
)


def render_annotation_legend() -> None:
    import html
    import streamlit as st

    items = "".join(
        f'<span><b class="{item.css_class}">{html.escape(item.symbol)}</b> {html.escape(item.label)}</span>'
        for item in ANNOTATION_LEGEND_ITEMS
    )
    st.markdown(
        f'<div class="mas-legend" aria-label="Annotation legend">{items}</div>',
        unsafe_allow_html=True,
    )
