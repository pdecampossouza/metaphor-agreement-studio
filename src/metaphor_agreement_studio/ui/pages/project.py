from __future__ import annotations

from pathlib import Path
import re

from metaphor_agreement_studio.persistence.backup import create_backup, restore_backup
from metaphor_agreement_studio.persistence.project_service import create_project, open_project
from metaphor_agreement_studio.state.session import (
    DATASET_STATUS_KEY,
    DATASET_VERSION_KEY,
    ANALYSIS_VERSION_KEY,
    PRIMARY_WORKBOOK_KEY,
    PROJECT_CONTEXT_KEY,
    PROJECT_NAME_KEY,
    VALIDATED_DATASET_KEY,
    WORKSPACE_MODE_KEY,
    set_project_context,
)
from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.error_boundary import render_user_error



def discover_project_roots(base_dir: Path) -> tuple[Path, ...]:
    base_dir = Path(base_dir).expanduser().resolve()
    candidates: list[Path] = []
    if (base_dir / "project.json").is_file() and (base_dir / "project.db").is_file():
        candidates.append(base_dir)
    projects_root = base_dir / "projects"
    if projects_root.is_dir():
        for child in sorted(projects_root.iterdir(), key=lambda item: item.name.casefold()):
            if child.is_dir() and (child / "project.json").is_file() and (child / "project.db").is_file():
                candidates.append(child.resolve())
    return tuple(candidates)


def discover_backup_archives(base_dir: Path) -> tuple[Path, ...]:
    base_dir = Path(base_dir).expanduser().resolve()
    return tuple(
        sorted(
            (path.resolve() for path in base_dir.rglob("*.masproject.zip") if path.is_file()),
            key=lambda item: str(item).casefold(),
        )
    )

def project_page_state(state) -> dict[str, object]:
    mode = state.get(WORKSPACE_MODE_KEY, "quick_analysis")
    context = state.get(PROJECT_CONTEXT_KEY)
    validated = state.get(DATASET_STATUS_KEY) == "validated" and state.get(VALIDATED_DATASET_KEY) is not None
    return {
        "mode": mode,
        "context": context,
        "can_save_as_project": mode == "quick_analysis" and context is None and validated,
        "can_backup": mode == "research_project" and context is not None,
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return slug or "metaphor_study"


def _source_paths(state) -> list[Path]:
    paths: list[Path] = []
    primary = state.get(PRIMARY_WORKBOOK_KEY)
    if primary is not None and getattr(primary, "local_path", None):
        paths.append(Path(primary.local_path))
    selected = state.get("selected_workbook_path")
    if selected:
        path = Path(selected)
        if path.exists() and path not in paths:
            paths.append(path)
    for item in state.get("additional_workbooks", []):
        path = getattr(item, "local_path", None)
        if path and Path(path) not in paths:
            paths.append(Path(path))
    return paths


def _apply_context(context, state) -> None:
    set_project_context(context, state)


def render_project(base_dir: Path) -> None:
    import streamlit as st

    page_header(
        "Project",
        "Move between temporary inspection and a persistent, reproducible research project.",
        (
            "Quick Analysis does not write a project database. Saving as a Research Project preserves "
            "source workbooks, validation decisions, dataset versions, analysis versions, and audit history locally."
        ),
    )
    view = project_page_state(st.session_state)
    context = view["context"]

    if view["mode"] == "quick_analysis":
        st.markdown("### Quick Analysis")
        st.caption("Temporary session · no persistent project history is being written.")
        if view["can_save_as_project"]:
            st.markdown("#### Save as Research Project")
            name = st.text_input("Project name", value="Metaphor Annotation Study")
            suggested = Path(base_dir) / "projects" / _slug(name)
            location = st.text_input("Project folder", value=str(suggested))
            st.caption("The project will be stored locally and can be copied or backed up later.")
            if st.button("Save as Research Project", type="primary", icon=":material/save:"):
                source_paths = _source_paths(st.session_state)
                if not source_paths:
                    st.warning("No source workbook is available to preserve with this project.")
                else:
                    try:
                        with st.spinner("Creating local research project..."):
                            created = create_project(
                                Path(location),
                                name,
                                st.session_state[VALIDATED_DATASET_KEY],
                                source_paths,
                            )
                        _apply_context(created, st.session_state)
                        st.rerun()
                    except Exception as exc:
                        render_user_error(
                            exc,
                            log_dir=Path(base_dir) / ".mas_logs",
                            context={"event_type": "project_create_failed"},
                        )
        else:
            st.info("Validate the dataset before saving this temporary analysis as a Research Project.")

        st.markdown("#### Open existing Research Project")
        saved_projects = discover_project_roots(base_dir)
        if saved_projects:
            selected_project = st.selectbox(
                "Saved project",
                saved_projects,
                format_func=lambda path: path.name.replace("_", " "),
            )
            if st.button("Open Project", icon=":material/folder_open:"):
                try:
                    opened = open_project(selected_project)
                    _apply_context(opened, st.session_state)
                    st.rerun()
                except Exception as exc:
                    render_user_error(
                        exc,
                        log_dir=Path(base_dir) / ".mas_logs",
                        context={"event_type": "project_open_failed"},
                    )
        else:
            st.caption("No saved Research Project was detected in the local projects folder.")

        with st.expander("Open a project from another folder"):
            project_path = st.text_input(
                "Existing project folder",
                value=str(Path(base_dir) / "projects"),
                key="open_project_path",
            )
            if st.button("Open folder as Project", icon=":material/folder_open:"):
                try:
                    opened = open_project(Path(project_path))
                    _apply_context(opened, st.session_state)
                    st.rerun()
                except Exception as exc:
                    render_user_error(
                        exc,
                        log_dir=Path(base_dir) / ".mas_logs",
                        context={"event_type": "project_folder_open_failed"},
                    )

        st.markdown("#### Restore portable backup")
        backups = discover_backup_archives(base_dir)
        if backups:
            selected_backup = st.selectbox(
                "Detected backup",
                backups,
                format_func=lambda path: path.name,
                key="detected_backup",
            )
            default_restore_name = selected_backup.name.removesuffix(".masproject.zip") + "_restored"
            restore_to = st.text_input(
                "Restore into folder",
                value=str(Path(base_dir) / "projects" / default_restore_name),
                key="restore_backup_destination",
            )
            if st.button("Restore Backup", icon=":material/restore:"):
                try:
                    restored = restore_backup(selected_backup, Path(restore_to))
                    _apply_context(restored, st.session_state)
                    st.rerun()
                except Exception as exc:
                    render_user_error(
                        exc,
                        log_dir=Path(base_dir) / ".mas_logs",
                        context={"event_type": "project_restore_failed"},
                    )
        else:
            st.caption("No .masproject.zip backup was detected in this workspace yet.")
        return

    if context is None:
        st.warning("Research Project mode is active, but no project context is loaded.")
        return

    st.markdown("### Project identity")
    cols = st.columns(4)
    cols[0].metric("Project", context.project.name)
    cols[1].metric(
        "Dataset",
        context.current_dataset_version.display_id if context.current_dataset_version else "—",
    )
    cols[2].metric(
        "Analysis",
        context.current_analysis_version.display_id if context.current_analysis_version else "Not run",
    )
    cols[3].metric("Raters", len(context.dataset.raters) if context.dataset else 0)

    st.markdown("### Source files")
    if context.source_files:
        for item in context.source_files:
            st.markdown(f"**{item.original_name}**  ")
            st.caption(f"Preserved copy · SHA-256 {item.sha256[:16]}… · {item.byte_length:,} bytes")
    else:
        st.caption("No source files are registered in this project.")

    st.markdown("### Dataset")
    if context.current_dataset_version:
        st.markdown(
            f"**{context.current_dataset_version.display_id}** · {context.current_dataset_version.reason}"
        )
        st.caption(f"Content hash: {context.current_dataset_version.content_hash}")

    st.markdown("### Analysis")
    if context.current_analysis_version:
        st.markdown(f"**{context.current_analysis_version.display_id}**")
        st.caption("Analysis configuration is versioned separately from the validated dataset.")
    else:
        st.caption("No persistent analysis version has been recorded yet.")

    st.markdown("### Backup")
    st.caption(
        "Create a portable .masproject.zip archive containing the project database, preserved source files, and current research outputs."
    )
    if st.button("Create Portable Backup", icon=":material/archive:"):
        try:
            archive = create_backup(context.root)
            st.info(f"Backup created: {archive.name}", icon=":material/check_circle:")
            st.caption(str(archive))
        except Exception as exc:
            render_user_error(
                exc,
                log_dir=Path(base_dir) / ".mas_logs",
                context={"event_type": "project_backup_failed"},
            )

    with st.expander("Technical project location"):
        st.code(str(context.root))
