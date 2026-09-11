from __future__ import annotations

from metaphor_agreement_studio.ui.components import page_header
from metaphor_agreement_studio.ui.navigation import Route

_PAGE_COPY: dict[Route, tuple[str, str, str]] = {
    Route.DATA_VALIDATION: (
        "Data Validation",
        "Verify how source workbooks are interpreted before analysis.",
        "This workspace will inspect workbook structure, annotation coding, category labels, and alignment warnings.",
    ),
    Route.ANNOTATIONS: (
        "Annotations",
        "Review rater decisions side by side.",
        "This workspace will show the validated annotation matrix with filters for source, category, rater, and classification.",
    ),
    Route.AGREEMENT: (
        "Agreement",
        "Pairwise and overall inter-rater agreement.",
        "This workspace will connect raw agreement, chance-corrected measures, and clear explanations of what each statistic means.",
    ),
    Route.DISAGREEMENT_REVIEW: (
        "Disagreement Review",
        "Inspect lexical units where raters made different decisions.",
        "This workspace will organize cases by disagreement pattern without treating any rater as ground truth.",
    ),
    Route.CATEGORIES: (
        "Grammatical Categories",
        "Compare agreement across parts of speech.",
        "This workspace will analyze Noun, Verb, Adjective, and other validated categories while making small-sample limitations visible.",
    ),
    Route.SOURCES: (
        "Source Groups",
        "Compare source tables and, later, songs and contextual groupings.",
        "This workspace will distinguish original sources from aggregate views so analytical units are not double counted.",
    ),
    Route.RATER_EXPLORER: (
        "Rater Explorer",
        "Focus on one rater and compare their pattern with the others.",
        "This workspace will describe divergence without implying that a lower-agreement rater is incorrect.",
    ),
    Route.STATISTICS: (
        "Statistical Analysis",
        "Detailed estimates, assumptions, tests, and diagnostic notes.",
        "This workspace will expose advanced statistical details while keeping the default interpretation approachable.",
    ),
    Route.FIGURES: (
        "Figures",
        "Interactive exploration and publication-ready scientific graphics.",
        "This workspace will separate interactive analysis from clean export figures suitable for academic documents.",
    ),
    Route.REPORTING: (
        "LaTeX & Reporting",
        "Generate traceable tables, captions, and statistical reporting text.",
        "This workspace will provide editable publication helpers tied to the validated dataset and analysis version.",
    ),
    Route.EXPORT: (
        "Export Center",
        "Create datasets, tables, figures, and reproducibility packages.",
        "This workspace will collect research outputs without changing the original source workbooks.",
    ),
    Route.PROJECT: (
        "Project",
        "Move from a temporary analysis to a persistent research project.",
        "This workspace will manage local project metadata, files, dataset versions, and resumable research sessions.",
    ),
    Route.AUDIT: (
        "Audit History",
        "Trace validation decisions and analytical changes over time.",
        "This workspace will provide a researcher-readable audit history rather than raw technical logs.",
    ),
    Route.SETTINGS: (
        "Settings",
        "Control local application and analysis preferences.",
        "This workspace will contain reproducibility-sensitive settings with clear defaults and explanations.",
    ),
}


def render_locked(route: Route) -> None:
    import streamlit as st

    title, subtitle, help_text = _PAGE_COPY[route]
    page_header(title, subtitle, help_text)
    st.info("Complete data validation first.", icon=":material/lock:")
    st.caption(
        "Statistical and publication workspaces use only the researcher-validated canonical dataset."
    )
