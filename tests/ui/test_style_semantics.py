from pathlib import Path


def test_research_ui_reserves_green_and_red_for_annotation_semantics() -> None:
    page_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/metaphor_agreement_studio/ui/pages").glob("*.py")
    )

    assert "st.success(" not in page_sources
    assert "st.error(" not in page_sources
