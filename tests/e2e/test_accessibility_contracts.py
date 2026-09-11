from __future__ import annotations

import ast
from pathlib import Path

from metaphor_agreement_studio.ui.legends import ANNOTATION_LEGEND_ITEMS


ANALYSIS_PAGES = (
    "agreement.py",
    "review.py",
    "categories.py",
    "sources.py",
    "rater_explorer.py",
    "statistics.py",
    "figures.py",
    "reporting.py",
    "export_center.py",
)


def _page_header_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "page_header"
    ]


def test_annotation_semantics_have_text_and_non_color_symbols() -> None:
    assert [item.label for item in ANNOTATION_LEGEND_ITEMS] == [
        "Metaphor",
        "Non-metaphor",
        "Missing / not rated",
        "Requires review",
    ]
    symbols = [item.symbol for item in ANNOTATION_LEGEND_ITEMS]
    assert all(symbol.strip() for symbol in symbols)
    assert len(set(symbols)) == len(symbols)


def test_every_analysis_page_supplies_how_to_read_help_text() -> None:
    root = Path("src/metaphor_agreement_studio/ui/pages")
    for filename in ANALYSIS_PAGES:
        calls = _page_header_calls(root / filename)
        assert calls, filename
        for call in calls:
            has_third_positional = len(call.args) >= 3
            has_help_keyword = any(keyword.arg == "help_text" for keyword in call.keywords)
            assert has_third_positional or has_help_keyword, filename


def test_form_labels_remain_visible_on_analysis_pages() -> None:
    root = Path("src/metaphor_agreement_studio/ui/pages")
    text = "\n".join((root / name).read_text(encoding="utf-8") for name in ANALYSIS_PAGES)
    assert 'label_visibility="collapsed"' not in text


def test_desktop_css_has_standard_and_narrow_breakpoints() -> None:
    css = Path("assets/styles.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1280px)" in css
    assert "@media (max-width: 900px)" in css
    assert ".mas-status-strip" in css


def test_publication_figures_do_not_depend_on_color_alone() -> None:
    source = Path("src/metaphor_agreement_studio/figures/publication.py").read_text(encoding="utf-8")
    assert 'markers = {"Metaphor": "o", "Non-metaphor": "x"}' in source
    assert "set_hatch" in source
    assert 'marker="D"' in source
    assert 'linestyle="--"' in source


def test_generic_validation_state_does_not_reuse_metaphor_semantic_green() -> None:
    css = Path("assets/styles.css").read_text(encoding="utf-8")
    metaphor_rule = ".mas-metaphor { background: var(--mas-metaphor); }"
    assert metaphor_rule in css
    assert ".mas-status-valid { color: #244f54" in css
    assert ".mas-status-valid { color: var(--mas-metaphor)" not in css
