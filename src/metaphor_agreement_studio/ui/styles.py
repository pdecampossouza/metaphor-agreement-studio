from pathlib import Path


def stylesheet_path() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "styles.css"


def load_styles() -> None:
    import streamlit as st

    path = stylesheet_path()
    if not path.exists():
        return
    st.markdown(f"<style>{path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
