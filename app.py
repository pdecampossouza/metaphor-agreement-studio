from __future__ import annotations

import os
from pathlib import Path

from metaphor_agreement_studio.config import APP_NAME
from metaphor_agreement_studio.state.session import current_route, ensure_session_state
from metaphor_agreement_studio.ui.navigation import render_route
from metaphor_agreement_studio.ui.error_boundary import render_user_error
from metaphor_agreement_studio.ui.shell import render_shell


def workspace_path() -> Path:
    configured = os.environ.get("MAS_WORKSPACE")
    return Path(configured if configured else Path.cwd()).resolve()


def main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title=APP_NAME,
        page_icon="♪",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_session_state()
    base_dir = workspace_path()

    def render_current_page() -> None:
        try:
            render_route(current_route(), base_dir)
        except Exception as exc:
            render_user_error(
                exc,
                log_dir=base_dir / ".mas_logs",
                context={"event_type": "page_render_failed"},
            )

    render_shell(render_current_page)


if __name__ == "__main__":
    main()
