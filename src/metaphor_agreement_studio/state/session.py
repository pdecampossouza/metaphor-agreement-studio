from typing import Any, MutableMapping

from metaphor_agreement_studio.ui.navigation import Route

ROUTE_KEY = "route"
DATASET_STATUS_KEY = "dataset_status"
PROJECT_NAME_KEY = "project_name"
DATASET_VERSION_KEY = "dataset_version"
ANALYSIS_VERSION_KEY = "analysis_version"
PRIMARY_WORKBOOK_KEY = "primary_workbook"
ADDITIONAL_WORKBOOKS_KEY = "additional_workbooks"
VALIDATION_DRAFT_KEY = "validation_draft"
VALIDATED_DATASET_KEY = "validated_dataset"
VALIDATION_DECISIONS_KEY = "validation_decisions"
PROJECT_CONTEXT_KEY = "project_context"
WORKSPACE_MODE_KEY = "workspace_mode"

DEFAULT_DATASET_STATUS = "not_validated"
DEFAULT_PROJECT_NAME = "Quick Analysis"


def _session_state() -> MutableMapping[str, Any]:
    import streamlit as st

    return st.session_state


def ensure_session_state(state: MutableMapping[str, Any] | None = None) -> None:
    target = state if state is not None else _session_state()
    target.setdefault(ROUTE_KEY, Route.OVERVIEW.value)
    target.setdefault(DATASET_STATUS_KEY, DEFAULT_DATASET_STATUS)
    target.setdefault(PROJECT_NAME_KEY, DEFAULT_PROJECT_NAME)
    target.setdefault(DATASET_VERSION_KEY, None)
    target.setdefault(ANALYSIS_VERSION_KEY, None)
    target.setdefault(PRIMARY_WORKBOOK_KEY, None)
    target.setdefault(ADDITIONAL_WORKBOOKS_KEY, [])
    target.setdefault(VALIDATION_DRAFT_KEY, None)
    target.setdefault(VALIDATED_DATASET_KEY, None)
    target.setdefault(VALIDATION_DECISIONS_KEY, [])
    target.setdefault(PROJECT_CONTEXT_KEY, None)
    target.setdefault(WORKSPACE_MODE_KEY, "quick_analysis")


def current_route(state: MutableMapping[str, Any] | None = None) -> Route:
    target = state if state is not None else _session_state()
    ensure_session_state(target)
    raw = target.get(ROUTE_KEY, Route.OVERVIEW.value)
    try:
        return Route(str(raw))
    except ValueError:
        target[ROUTE_KEY] = Route.OVERVIEW.value
        return Route.OVERVIEW


def set_route(route: Route, state: MutableMapping[str, Any] | None = None) -> None:
    target = state if state is not None else _session_state()
    ensure_session_state(target)
    target[ROUTE_KEY] = route.value


def set_primary_workbook(workbook, state: MutableMapping[str, Any] | None = None) -> None:
    target = state if state is not None else _session_state()
    ensure_session_state(target)
    target[PRIMARY_WORKBOOK_KEY] = workbook
    target[VALIDATION_DRAFT_KEY] = None
    target[VALIDATED_DATASET_KEY] = None
    target[DATASET_STATUS_KEY] = DEFAULT_DATASET_STATUS


def add_additional_workbook(workbook, state: MutableMapping[str, Any] | None = None) -> None:
    target = state if state is not None else _session_state()
    ensure_session_state(target)
    existing = list(target.get(ADDITIONAL_WORKBOOKS_KEY, []))
    if workbook not in existing:
        existing.append(workbook)
    target[ADDITIONAL_WORKBOOKS_KEY] = existing
    target[VALIDATED_DATASET_KEY] = None
    target[DATASET_STATUS_KEY] = DEFAULT_DATASET_STATUS


def set_project_context(context, state: MutableMapping[str, Any] | None = None) -> None:
    target = state if state is not None else _session_state()
    ensure_session_state(target)
    target[PROJECT_CONTEXT_KEY] = context
    if context is None:
        target[WORKSPACE_MODE_KEY] = "quick_analysis"
        target[PROJECT_NAME_KEY] = DEFAULT_PROJECT_NAME
        target[DATASET_VERSION_KEY] = None
        target[ANALYSIS_VERSION_KEY] = None
        return
    target[WORKSPACE_MODE_KEY] = "research_project"
    target[PROJECT_NAME_KEY] = context.project.name
    target[VALIDATED_DATASET_KEY] = context.dataset
    target[DATASET_STATUS_KEY] = "validated" if context.dataset is not None else DEFAULT_DATASET_STATUS
    target[DATASET_VERSION_KEY] = (
        context.current_dataset_version.display_id if context.current_dataset_version else None
    )
    target[ANALYSIS_VERSION_KEY] = (
        context.current_analysis_version.display_id if context.current_analysis_version else None
    )
    target[PRIMARY_WORKBOOK_KEY] = None
    target[ADDITIONAL_WORKBOOKS_KEY] = []
    target[VALIDATION_DRAFT_KEY] = None
    target[VALIDATION_DECISIONS_KEY] = list(
        getattr(context.dataset, "validation_decisions", ()) if context.dataset is not None else ()
    )
    target["selected_workbook_path"] = None
