from metaphor_agreement_studio.ui.navigation import NAV_SECTIONS, Route


def test_navigation_contains_approved_information_architecture() -> None:
    labels = [item.label for section in NAV_SECTIONS for item in section.items]
    assert labels == [
        "Overview",
        "Data Validation",
        "Annotations",
        "Agreement",
        "Disagreement Review",
        "Grammatical Categories",
        "Source Groups",
        "Rater Explorer",
        "Statistical Analysis",
        "Figures",
        "LaTeX & Reporting",
        "Export Center",
        "Project",
        "Audit History",
        "Settings",
    ]
    assert Route.OVERVIEW.value == "overview"


def test_navigation_groups_match_research_workstation_sections() -> None:
    assert [section.label for section in NAV_SECTIONS] == [
        "OVERVIEW",
        "DATA",
        "ANALYSIS",
        "PUBLICATION",
        "PROJECT",
    ]


def test_session_defaults_and_route_recovery() -> None:
    from metaphor_agreement_studio.state.session import (
        DATASET_STATUS_KEY,
        PROJECT_NAME_KEY,
        ROUTE_KEY,
        current_route,
        ensure_session_state,
        set_route,
    )

    state: dict[str, object] = {}
    ensure_session_state(state)
    assert state[ROUTE_KEY] == Route.OVERVIEW.value
    assert state[DATASET_STATUS_KEY] == "not_validated"
    assert state[PROJECT_NAME_KEY] == "Quick Analysis"

    set_route(Route.FIGURES, state)
    assert current_route(state) is Route.FIGURES

    state[ROUTE_KEY] = "unknown-route"
    assert current_route(state) is Route.OVERVIEW
    assert state[ROUTE_KEY] == Route.OVERVIEW.value


def test_set_project_context_updates_workspace_versions_and_dataset(tmp_path) -> None:
    from metaphor_agreement_studio.persistence.types import (
        AnalysisVersionRecord,
        DatasetVersionRecord,
        ProjectContext,
        ProjectRecord,
    )
    from metaphor_agreement_studio.state.session import (
        ANALYSIS_VERSION_KEY,
        DATASET_STATUS_KEY,
        DATASET_VERSION_KEY,
        PROJECT_CONTEXT_KEY,
        PROJECT_NAME_KEY,
        VALIDATED_DATASET_KEY,
        WORKSPACE_MODE_KEY,
        set_project_context,
    )

    dataset = object()
    context = ProjectContext(
        tmp_path,
        ProjectRecord("p1", "Study", "now", "now", "0.5.0"),
        DatasetVersionRecord("d1", 1, "now", "initial", "hash", "{}"),
        AnalysisVersionRecord("a1", 1, "d1", "now", "{}", "cfg"),
        dataset=dataset,
    )
    state = {
        "primary_workbook": object(),
        "additional_workbooks": [object()],
        "validation_draft": object(),
        "validation_decisions": [object()],
        "selected_workbook_path": "old.xlsx",
    }
    set_project_context(context, state)

    assert state[PROJECT_CONTEXT_KEY] is context
    assert state[WORKSPACE_MODE_KEY] == "research_project"
    assert state[PROJECT_NAME_KEY] == "Study"
    assert state[VALIDATED_DATASET_KEY] is dataset
    assert state[DATASET_STATUS_KEY] == "validated"
    assert state[DATASET_VERSION_KEY] == "v1.0"
    assert state[ANALYSIS_VERSION_KEY] == "A-001"
    assert state["primary_workbook"] is None
    assert state["additional_workbooks"] == []
    assert state["validation_draft"] is None
    assert state["selected_workbook_path"] is None
