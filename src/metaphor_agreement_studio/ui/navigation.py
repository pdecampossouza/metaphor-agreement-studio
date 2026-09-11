from dataclasses import dataclass
from enum import StrEnum


class Route(StrEnum):
    OVERVIEW = "overview"
    DATA_VALIDATION = "data-validation"
    ANNOTATIONS = "annotations"
    AGREEMENT = "agreement"
    DISAGREEMENT_REVIEW = "disagreement-review"
    CATEGORIES = "grammatical-categories"
    SOURCES = "source-groups"
    RATER_EXPLORER = "rater-explorer"
    STATISTICS = "statistical-analysis"
    FIGURES = "figures"
    REPORTING = "latex-reporting"
    EXPORT = "export-center"
    PROJECT = "project"
    AUDIT = "audit-history"
    SETTINGS = "settings"


@dataclass(frozen=True, slots=True)
class NavItem:
    route: Route
    label: str
    icon: str


@dataclass(frozen=True, slots=True)
class NavSection:
    label: str
    items: tuple[NavItem, ...]


_LOCKED_ROUTES = {
    Route.AGREEMENT,
    Route.DISAGREEMENT_REVIEW,
    Route.CATEGORIES,
    Route.SOURCES,
    Route.RATER_EXPLORER,
    Route.STATISTICS,
    Route.FIGURES,
    Route.REPORTING,
    Route.EXPORT,
}


def route_requires_validated_dataset(route: Route) -> bool:
    return route in _LOCKED_ROUTES


NAV_SECTIONS = (
    NavSection("OVERVIEW", (NavItem(Route.OVERVIEW, "Overview", "home"),)),
    NavSection(
        "DATA",
        (
            NavItem(Route.DATA_VALIDATION, "Data Validation", "fact_check"),
            NavItem(Route.ANNOTATIONS, "Annotations", "table_view"),
        ),
    ),
    NavSection(
        "ANALYSIS",
        (
            NavItem(Route.AGREEMENT, "Agreement", "handshake"),
            NavItem(Route.DISAGREEMENT_REVIEW, "Disagreement Review", "manage_search"),
            NavItem(Route.CATEGORIES, "Grammatical Categories", "category"),
            NavItem(Route.SOURCES, "Source Groups", "library_music"),
            NavItem(Route.RATER_EXPLORER, "Rater Explorer", "groups"),
            NavItem(Route.STATISTICS, "Statistical Analysis", "functions"),
        ),
    ),
    NavSection(
        "PUBLICATION",
        (
            NavItem(Route.FIGURES, "Figures", "insert_chart"),
            NavItem(Route.REPORTING, "LaTeX & Reporting", "description"),
            NavItem(Route.EXPORT, "Export Center", "download"),
        ),
    ),
    NavSection(
        "PROJECT",
        (
            NavItem(Route.PROJECT, "Project", "folder"),
            NavItem(Route.AUDIT, "Audit History", "history"),
            NavItem(Route.SETTINGS, "Settings", "settings"),
        ),
    ),
)


def render_route(route: Route, base_dir):
    from metaphor_agreement_studio.ui.pages.agreement import render_agreement
    from metaphor_agreement_studio.ui.pages.annotations import render_annotations
    from metaphor_agreement_studio.ui.pages.categories import render_categories
    from metaphor_agreement_studio.ui.pages.overview import render_overview
    from metaphor_agreement_studio.ui.pages.figures import render_figures
    from metaphor_agreement_studio.ui.pages.reporting import render_reporting
    from metaphor_agreement_studio.ui.pages.export_center import render_export_center
    from metaphor_agreement_studio.ui.pages.placeholders import render_locked
    from metaphor_agreement_studio.ui.pages.rater_explorer import render_rater_explorer
    from metaphor_agreement_studio.ui.pages.review import render_review
    from metaphor_agreement_studio.ui.pages.sources import render_sources
    from metaphor_agreement_studio.ui.pages.statistics import render_statistics
    from metaphor_agreement_studio.ui.pages.validation import render_validation

    if route is Route.OVERVIEW:
        render_overview(base_dir)
        return
    if route is Route.DATA_VALIDATION:
        render_validation(base_dir)
        return
    if route is Route.ANNOTATIONS:
        render_annotations()
        return
    if route in {
        Route.AGREEMENT,
        Route.DISAGREEMENT_REVIEW,
        Route.CATEGORIES,
        Route.SOURCES,
        Route.RATER_EXPLORER,
        Route.STATISTICS,
    }:
        import streamlit as st

        if st.session_state.get("dataset_status") != "validated":
            render_locked(route)
            return
        renderers = {
            Route.AGREEMENT: render_agreement,
            Route.DISAGREEMENT_REVIEW: render_review,
            Route.CATEGORIES: render_categories,
            Route.SOURCES: render_sources,
            Route.RATER_EXPLORER: render_rater_explorer,
            Route.STATISTICS: render_statistics,
        }
        renderers[route]()
        return
    if route_requires_validated_dataset(route):
        import streamlit as st

        if st.session_state.get("dataset_status") != "validated":
            render_locked(route)
            return
    if route is Route.FIGURES:
        render_figures()
        return
    if route is Route.REPORTING:
        render_reporting()
        return
    if route is Route.EXPORT:
        render_export_center()
        return
    if route is Route.PROJECT:
        from metaphor_agreement_studio.ui.pages.project import render_project
        render_project(base_dir)
        return
    if route is Route.AUDIT:
        from metaphor_agreement_studio.ui.pages.audit import render_audit
        render_audit()
        return
    if route is Route.SETTINGS:
        from metaphor_agreement_studio.ui.pages.settings import render_settings
        render_settings()
        return
    raise ValueError(f"Unsupported application route: {route}")
