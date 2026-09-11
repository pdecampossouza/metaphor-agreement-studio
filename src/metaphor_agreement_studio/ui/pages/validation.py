from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile

from metaphor_agreement_studio.config import default_scan_roots
from metaphor_agreement_studio.domain.enums import Classification, IssueSeverity
from metaphor_agreement_studio.domain.imports import ValidationDecision, ValidationDraft
from metaphor_agreement_studio.import_engine.discovery import discover_workbooks
from metaphor_agreement_studio.import_engine.mappings import classify_cell
from metaphor_agreement_studio.import_engine.uploads import UnsupportedWorkbookError, materialize_upload
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook_cached
from metaphor_agreement_studio.persistence.project_service import save_dataset_version
from metaphor_agreement_studio.state.session import (
    ADDITIONAL_WORKBOOKS_KEY,
    DATASET_STATUS_KEY,
    PRIMARY_WORKBOOK_KEY,
    VALIDATED_DATASET_KEY,
    VALIDATION_DECISIONS_KEY,
    VALIDATION_DRAFT_KEY,
    PROJECT_CONTEXT_KEY,
    WORKSPACE_MODE_KEY,
    set_project_context,
    add_additional_workbook,
    set_primary_workbook,
)
from metaphor_agreement_studio.ui.components import page_header, semantic_legend
from metaphor_agreement_studio.ui.error_boundary import render_user_error
from metaphor_agreement_studio.validation.service import ValidationBlocked, ValidationService


def worksheet_role_sheet_names(draft: ValidationDraft) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(table.sheet_name for table in draft.tables))
    return names if len(names) > 1 else ()


def validation_scope_for_worksheet_roles(
    draft: ValidationDraft,
    worksheet_roles: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    study_sheets = tuple(
        sheet_name
        for sheet_name in worksheet_role_sheet_names(draft)
        if worksheet_roles.get(sheet_name) == "study_data"
    )
    if not worksheet_role_sheet_names(draft):
        study_sheets = tuple(dict.fromkeys(table.sheet_name for table in draft.tables))
    study_set = set(study_sheets)
    active_tables = tuple(table for table in draft.tables if table.sheet_name in study_set)
    table_ids = tuple(table.table_id for table in active_tables)
    rater_names_seen = {
        rater.display_name.casefold()
        for table in active_tables
        for rater in table.rater_columns
    }
    active_mappings = tuple(
        mapping
        for mapping in draft.rater_mappings
        if mapping.display_name.casefold() in rater_names_seen
    )
    active_table_id_set = set(table_ids)
    aggregate_ids = tuple(
        candidate.aggregate_table_id
        for candidate in draft.aggregate_candidates
        if candidate.aggregate_table_id in active_table_id_set
    )
    category_labels = tuple(
        dict.fromkeys(
            row.grammatical_category
            for table in active_tables
            for row in table.rows
        )
    )
    return {
        "study_sheets": study_sheets,
        "table_ids": table_ids,
        "rater_names": tuple(mapping.display_name for mapping in active_mappings),
        "rater_ids": tuple(mapping.rater_id for mapping in active_mappings),
        "aggregate_ids": aggregate_ids,
        "category_labels": category_labels,
    }


def validation_summary(draft: ValidationDraft) -> dict[str, object]:
    style_values = {
        value
        for rater in draft.rater_mappings
        for value in rater.mapping_candidate.evidence.color_values
    }
    return {
        "workbook": draft.inspection.path.name,
        "worksheets": len(draft.inspection.sheets),
        "tables": len(draft.tables),
        "raters": tuple(rater.display_name for rater in draft.rater_mappings),
        "style_groups": len(style_values),
        "normalization_count": len(draft.normalization_proposals),
        "aggregate_count": len(draft.aggregate_candidates),
        "blocking_issues": sum(issue.blocks_validation for issue in draft.issues),
    }


def _project_source_paths(state) -> tuple[Path, ...]:
    paths: list[Path] = []
    primary = state.get(PRIMARY_WORKBOOK_KEY)
    if primary is not None and getattr(primary, "local_path", None):
        paths.append(Path(primary.local_path))
    selected = state.get("selected_workbook_path")
    if selected and Path(selected).exists():
        path = Path(selected)
        if path not in paths:
            paths.append(path)
    for item in state.get(ADDITIONAL_WORKBOOKS_KEY, []):
        raw = getattr(item, "local_path", None)
        if raw and Path(raw) not in paths:
            paths.append(Path(raw))
    return tuple(paths)


def persist_validated_dataset_if_project(state, dataset):
    if state.get(WORKSPACE_MODE_KEY) != "research_project":
        return None
    context = state.get(PROJECT_CONTEXT_KEY)
    if context is None:
        return None
    updated = save_dataset_version(
        context,
        dataset,
        "Validated dataset updated from Data Validation",
        source_paths=_project_source_paths(state),
    )
    set_project_context(updated, state)
    return updated


def _upload_root() -> Path:
    return Path(tempfile.gettempdir()) / "metaphor_agreement_studio" / "uploads"


def _active_local_path(base_dir: Path):
    import streamlit as st

    primary = st.session_state.get(PRIMARY_WORKBOOK_KEY)
    if primary is not None:
        return primary.local_path
    selected = st.session_state.get("selected_workbook_path")
    if selected:
        path = Path(selected)
        if path.exists():
            return path.resolve()
    candidates = discover_workbooks(default_scan_roots(base_dir))
    return candidates[0].path if candidates else None


def _ensure_draft(path: Path) -> ValidationDraft | None:
    import streamlit as st

    draft = st.session_state.get(VALIDATION_DRAFT_KEY)
    if draft is not None and draft.inspection.path == path.resolve():
        return draft
    try:
        with st.spinner("Inspecting workbook structure and annotation evidence..."):
            inspection = inspect_workbook_cached(path)
            draft = ValidationService().prepare(inspection)
        st.session_state[VALIDATION_DRAFT_KEY] = draft
        st.session_state[VALIDATED_DATASET_KEY] = None
        st.session_state[DATASET_STATUS_KEY] = "not_validated"
        return draft
    except Exception as exc:
        render_user_error(exc, context={"event_type": "workbook_inspection_failed", "source_filename": path.name})
        return None


def _issue_label(severity: IssueSeverity) -> str:
    if severity == IssueSeverity.REQUIRES_ACTION:
        return "Requires action"
    if severity == IssueSeverity.WARNING:
        return "Warning"
    return "Information"


def _make_decision(
    decision_type: str,
    target_id: str,
    original_value: str | None,
    validated_value: str | None,
    reason: str,
) -> ValidationDecision:
    return ValidationDecision(
        decision_id=f"ui:{decision_type}:{target_id}",
        decision_type=decision_type,
        target_id=target_id,
        original_value=original_value,
        validated_value=validated_value,
        reason=reason,
        decided_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )


def source_summary_records(
    draft: ValidationDraft,
    worksheet_roles: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    worksheet_roles = worksheet_roles or {}
    role_labels = {
        "study_data": "Study data",
        "synthetic_example": "Synthetic / example — excluded",
        "ignore": "Ignored",
    }
    aggregate_ids = {candidate.aggregate_table_id for candidate in draft.aggregate_candidates}
    records: list[dict[str, object]] = []
    for table in draft.tables:
        records.append(
            {
                "Source": table.source_title,
                "Worksheet": table.sheet_name,
                "Worksheet role": role_labels.get(worksheet_roles.get(table.sheet_name, ""), "Not selected"),
                "Rows": table.row_count,
                "Raters": ", ".join(r.display_name for r in table.rater_columns),
                "Detected role": "Potential aggregate" if table.table_id in aggregate_ids else "Source",
                "Range": f"row {table.data_start_row}–{table.data_end_row}",
            }
        )
    return records


def _render_source_summary(
    draft: ValidationDraft,
    worksheet_roles: dict[str, str] | None = None,
) -> None:
    import pandas as pd
    import streamlit as st

    st.markdown("#### Detected source tables")
    st.dataframe(
        pd.DataFrame(source_summary_records(draft, worksheet_roles)),
        use_container_width=True,
        hide_index=True,
    )


def _render_provenance_inspector(
    draft: ValidationDraft,
    allowed_table_ids: set[str] | None = None,
) -> None:
    import streamlit as st

    with st.expander("Annotation provenance inspector", icon=":material/troubleshoot:"):
        st.caption(
            "Use this inspector to verify exactly where an interpreted annotation came from in Excel."
        )
        tables = tuple(
            table
            for table in draft.tables
            if allowed_table_ids is None or table.table_id in allowed_table_ids
        )
        if not tables:
            st.caption("No study-data source table is available for provenance inspection.")
            return
        table = st.selectbox(
            "Source table",
            tables,
            format_func=lambda item: item.source_title,
            key="provenance_table",
        )
        if not table.rows:
            return
        row = st.selectbox(
            "Lexical unit",
            table.rows,
            format_func=lambda item: f"{item.order}. {item.lexical_unit} · {item.grammatical_category}",
            key="provenance_row",
        )
        rater = st.selectbox(
            "Rater",
            table.rater_columns,
            format_func=lambda item: item.display_name,
            key="provenance_rater",
        )
        rater_index = table.rater_columns.index(rater)
        cell = row.annotation_cells[rater_index]
        mapping = next(
            item.mapping_candidate
            for item in draft.rater_mappings
            if item.display_name.casefold() == rater.display_name.casefold()
        )
        classification, method = classify_cell(
            cell, mapping, workbook_theme=draft.inspection.workbook_theme
        )
        label = {
            Classification.METAPHOR: "Metaphor",
            Classification.NON_METAPHOR: "Non-metaphor",
            Classification.MISSING: "Missing",
        }[classification]
        details = {
            "Lexical unit": row.lexical_unit,
            "Grammatical category": row.grammatical_category,
            "Rater": rater.display_name,
            "Detected classification": label,
            "Workbook": draft.inspection.path.name,
            "Worksheet": table.sheet_name,
            "Source table": table.source_title,
            "Original cell": cell.coordinate,
            "Detection method": method,
            "Original value": repr(cell.raw_value),
            "Fill type": cell.fill.fill_type or "None",
            "Fill RGB": cell.fill.fg_rgb or "—",
            "Fill theme": cell.fill.fg_theme if cell.fill.fg_theme is not None else "—",
        }
        left, right = st.columns(2)
        for index, (key, value) in enumerate(details.items()):
            (left if index % 2 == 0 else right).markdown(f"**{key}**  \n{value}")


def _render_additional_raters(draft: ValidationDraft) -> None:
    import streamlit as st

    uploads = st.session_state.get(ADDITIONAL_WORKBOOKS_KEY, [])
    if not uploads:
        return

    from metaphor_agreement_studio.validation.rater_growth import (
        RaterMergeBlocked,
        align_validated_datasets,
        merge_additional_raters,
    )

    canonical = st.session_state.get(VALIDATED_DATASET_KEY)
    st.markdown("#### Additional rater files")
    st.caption(
        "Additional files are inspected and validated separately. Probable matches are never accepted automatically."
    )
    if canonical is None:
        st.info(
            "Validate the primary workbook first. Additional files can be inspected now, but they can only be merged into a canonical validated dataset.",
            icon=":material/info:",
        )

    def decision_controls(incoming_draft: ValidationDraft, prefix: str):
        decisions: list[ValidationDecision] = []
        unresolved = 0
        blocking = {
            (issue.decision_type, issue.target_id): issue
            for issue in incoming_draft.issues
            if issue.blocks_validation
        }
        for mapping in incoming_draft.rater_mappings:
            if ("annotation_mapping", mapping.rater_id) not in blocking:
                continue
            choice = st.selectbox(
                f"Confirm coding for {mapping.display_name}",
                [
                    "Choose coding...",
                    "Green = Metaphor; Red = Non-metaphor",
                    "Green = Non-metaphor; Red = Metaphor",
                    "Use recognized text labels as primary evidence",
                ],
                key=f"{prefix}_mapping_{mapping.rater_id}",
            )
            values = {
                "Green = Metaphor; Red = Non-metaphor": "confirm_green_metaphor_red_non_metaphor",
                "Green = Non-metaphor; Red = Metaphor": "green_non_metaphor_red_metaphor",
                "Use recognized text labels as primary evidence": "use_labels",
            }
            if choice in values:
                decisions.append(
                    _make_decision(
                        "annotation_mapping",
                        mapping.rater_id,
                        None,
                        values[choice],
                        "Researcher confirmed coding for an additional rater file.",
                    )
                )
            else:
                unresolved += 1

        for proposal in incoming_draft.normalization_proposals:
            choice = st.selectbox(
                f"Normalize {proposal.original} → {proposal.proposed}",
                ["Choose...", f"Accept {proposal.proposed}", f"Keep original: {proposal.original}"],
                key=f"{prefix}_normalization_{proposal.original}",
            )
            if choice == f"Accept {proposal.proposed}":
                decisions.append(
                    _make_decision(
                        "category_normalization",
                        proposal.original,
                        proposal.original,
                        proposal.proposed,
                        proposal.reason,
                    )
                )
            elif choice == f"Keep original: {proposal.original}":
                decisions.append(
                    _make_decision(
                        "category_normalization",
                        proposal.original,
                        proposal.original,
                        "KEEP_ORIGINAL",
                        "Researcher chose to preserve the original category label.",
                    )
                )
            else:
                unresolved += 1

        for candidate in incoming_draft.aggregate_candidates:
            choice = st.selectbox(
                f"Role for {candidate.aggregate_source_title}",
                ["Choose...", "Treat as aggregate (recommended)", "Treat as independent source"],
                key=f"{prefix}_aggregate_{candidate.aggregate_table_id}",
            )
            if choice == "Treat as aggregate (recommended)":
                decisions.append(
                    _make_decision(
                        "aggregate_role",
                        candidate.aggregate_table_id,
                        None,
                        "aggregate",
                        "Researcher confirmed aggregate role for an additional rater file.",
                    )
                )
            elif choice == "Treat as independent source":
                decisions.append(
                    _make_decision(
                        "aggregate_role",
                        candidate.aggregate_table_id,
                        None,
                        "independent",
                        "Researcher chose an independent source role for the additional rater file.",
                    )
                )
            else:
                unresolved += 1
        return tuple(decisions), unresolved

    for upload_index, upload in enumerate(uploads):
        prefix = f"additional_{upload.sha256[:12]}_{upload_index}"
        with st.container(border=True):
            st.markdown(f"**{upload.original_display_name}**")
            try:
                inspection = inspect_workbook_cached(upload.local_path)
                incoming_draft = ValidationService().prepare(inspection)
                cols = st.columns(3)
                cols[0].metric("Tables", len(incoming_draft.tables))
                cols[1].metric("Raters detected", len(incoming_draft.rater_mappings))
                cols[2].metric(
                    "Actions required",
                    sum(issue.blocks_validation for issue in incoming_draft.issues),
                )

                if canonical is None:
                    st.caption(
                        "This file remains separate until the primary dataset is validated. No annotation has been merged."
                    )
                    continue

                existing_names = {r.display_name.casefold() for r in canonical.raters}
                new_names = [
                    r.display_name
                    for r in incoming_draft.rater_mappings
                    if r.display_name.casefold() not in existing_names
                ]
                if not new_names:
                    st.info("All raters in this file are already present in the validated dataset.")
                    continue
                st.caption("New rater candidate(s): " + ", ".join(new_names))

                incoming_decisions, unresolved = decision_controls(incoming_draft, prefix)
                if unresolved:
                    st.caption(
                        f"{unresolved} validation decision(s) must be confirmed before unit alignment can be committed."
                    )
                    continue

                incoming_dataset = ValidationService().validate(
                    incoming_draft, incoming_decisions
                )
                alignment = align_validated_datasets(canonical, incoming_dataset)
                summary_cols = st.columns(3)
                summary_cols[0].metric("Exact matches", len(alignment.exact))
                summary_cols[1].metric("Probable", len(alignment.probable))
                summary_cols[2].metric("No match", len(alignment.no_match))

                accepted_probable: list[str] = []
                for match in alignment.probable:
                    reference_label = (
                        match.reference.lexical_unit if match.reference is not None else "No match"
                    )
                    accepted = st.checkbox(
                        (
                            f"Accept probable match: {match.incoming.lexical_unit} → {reference_label} "
                            f"({match.similarity:.0%} similarity)"
                        ),
                        value=False,
                        key=f"{prefix}_probable_{match.incoming.unit_id}",
                        help=(
                            "The Studio never commits a punctuation/fuzzy match automatically. "
                            "Confirm only when these are the same lexical occurrence."
                        ),
                    )
                    if accepted:
                        accepted_probable.append(match.incoming.unit_id)

                if alignment.no_match:
                    st.warning(
                        "At least one lexical unit has no safe match. Resolve the source file before adding this rater.",
                        icon=":material/rule:",
                    )
                    for match in alignment.no_match[:10]:
                        st.caption(
                            f"No match · {match.incoming.source_identity} · {match.incoming.lexical_unit} · {match.incoming.grammatical_category}"
                        )

                unresolved_probable = len(alignment.probable) - len(accepted_probable)
                disabled = bool(alignment.no_match or unresolved_probable)
                if st.button(
                    "Add validated rater",
                    key=f"{prefix}_commit",
                    type="primary",
                    icon=":material/person_add:",
                    disabled=disabled,
                ):
                    merged = merge_additional_raters(
                        canonical,
                        incoming_dataset,
                        alignment,
                        accepted_probable_incoming_ids=tuple(accepted_probable),
                    )
                    st.session_state[VALIDATED_DATASET_KEY] = merged
                    st.session_state[DATASET_STATUS_KEY] = "validated"
                    st.session_state.pop("phase3_analysis_cache", None)
                    persist_validated_dataset_if_project(st.session_state, merged)
                    st.info(
                        f"Validated rater added. The dataset now contains {len(merged.raters)} raters.",
                        icon=":material/person_add:",
                    )
                    st.rerun()
            except RaterMergeBlocked as exc:
                render_user_error(exc, context={"event_type": "additional_rater_merge_blocked"})
            except Exception as exc:
                render_user_error(
                    exc,
                    context={
                        "event_type": "additional_rater_inspection_failed",
                        "source_filename": upload.original_display_name,
                    },
                )


def render_validation(base_dir: Path) -> None:
    import streamlit as st

    page_header(
        "Data Validation",
        "Verify how source workbooks are interpreted before analysis.",
        (
            "The Studio detects tables, raters, annotation coding, grammatical categories, and aggregate views. "
            "Detection is only a proposal: you validate the interpretation before statistical analysis becomes available."
        ),
    )
    semantic_legend()
    st.info("Please verify the extracted data before running the analysis.", icon=":material/fact_check:")

    upload_cols = st.columns(2)
    primary_upload = upload_cols[0].file_uploader(
        "Upload workbook",
        type=["xlsx", "xlsm"],
        help="Use this when the primary workbook is not already in the Studio folder.",
        key="primary_workbook_upload",
    )
    additional_uploads = upload_cols[1].file_uploader(
        "Add rater files",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True,
        help="Additional evaluator files are inspected and aligned before any merge is allowed.",
        key="additional_rater_uploads",
    )

    if primary_upload is not None:
        try:
            materialized = materialize_upload(
                primary_upload.name, primary_upload.getvalue(), _upload_root()
            )
            if st.session_state.get(PRIMARY_WORKBOOK_KEY) != materialized:
                set_primary_workbook(materialized)
                st.session_state["selected_workbook_path"] = str(materialized.local_path)
        except UnsupportedWorkbookError as exc:
            st.warning(str(exc))

    for uploaded in additional_uploads or []:
        try:
            materialized = materialize_upload(uploaded.name, uploaded.getvalue(), _upload_root())
            add_additional_workbook(materialized)
        except UnsupportedWorkbookError as exc:
            st.warning(f"{uploaded.name}: {exc}")

    active_path = _active_local_path(base_dir)
    if active_path is None:
        st.warning(
            "No workbook is available yet. Upload one above or place an .xlsx/.xlsm file in the imports folder.",
            icon=":material/upload_file:",
        )
        return

    st.caption(f"Active workbook: **{active_path.name}**")
    draft = _ensure_draft(active_path)
    if draft is None:
        return

    summary = validation_summary(draft)
    st.markdown(
        f"""
        <div class="mas-stat-grid">
          <div class="mas-stat"><div class="mas-stat-label">Worksheets</div><div class="mas-stat-value">{summary['worksheets']}</div><div class="mas-stat-note">Workbook structure inspected</div></div>
          <div class="mas-stat"><div class="mas-stat-label">Annotation tables</div><div class="mas-stat-value">{summary['tables']}</div><div class="mas-stat-note">Detected semantically, not by fixed columns</div></div>
          <div class="mas-stat"><div class="mas-stat-label">Raters</div><div class="mas-stat-value">{len(summary['raters'])}</div><div class="mas-stat-note">{', '.join(summary['raters'])}</div></div>
          <div class="mas-stat"><div class="mas-stat-label">Actions required</div><div class="mas-stat-value">{summary['blocking_issues']}</div><div class="mas-stat-note">Must be resolved before validation</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    decisions: list[ValidationDecision] = []
    unresolved_controls = 0
    worksheet_roles: dict[str, str] = {}
    role_sheet_names = worksheet_role_sheet_names(draft)
    if role_sheet_names:
        st.markdown("#### Worksheet roles")
        st.caption(
            "Choose the research role of every worksheet before annotation coding is interpreted. "
            "Synthetic/example and ignored worksheets are excluded from validated research results."
        )
        role_options = [
            "Choose role...",
            "Study data",
            "Synthetic / example data",
            "Ignore",
        ]
        role_values = {
            "Study data": "study_data",
            "Synthetic / example data": "synthetic_example",
            "Ignore": "ignore",
        }
        for sheet_name in role_sheet_names:
            choice = st.selectbox(
                f"Role for worksheet: {sheet_name}",
                role_options,
                key=f"worksheet_role_{sheet_name}",
                help=(
                    "Study data contributes to analyses. Synthetic/example data remains available in the source workbook "
                    "but is never included in research statistics. Ignore excludes the worksheet entirely."
                ),
            )
            value = role_values.get(choice)
            if value:
                worksheet_roles[sheet_name] = value
                decisions.append(
                    _make_decision(
                        "worksheet_role",
                        sheet_name,
                        sheet_name,
                        value,
                        "Researcher confirmed the worksheet role in Data Validation.",
                    )
                )
            else:
                unresolved_controls += 1
        _render_source_summary(draft, worksheet_roles)
        if len(worksheet_roles) != len(role_sheet_names):
            st.info(
                "Choose a role for every worksheet to continue with annotation coding.",
                icon=":material/layers:",
            )
            return
        draft = ValidationService().prepare_for_worksheet_roles(
            draft.inspection, worksheet_roles
        )
    else:
        _render_source_summary(draft)

    blocking_by_target = {
        (issue.decision_type, issue.target_id): issue
        for issue in draft.issues
        if issue.blocks_validation
    }
    scope = validation_scope_for_worksheet_roles(draft, worksheet_roles)
    active_rater_ids = set(scope["rater_ids"])
    active_table_ids = set(scope["table_ids"])
    active_categories = set(scope["category_labels"])
    if not scope["study_sheets"]:
        st.warning(
            "At least one worksheet must be designated as Study data before validation.",
            icon=":material/rule:",
        )
        unresolved_controls += 1

    st.markdown("#### Annotation coding")
    for mapping in draft.rater_mappings:
        if mapping.rater_id not in active_rater_ids:
            continue
        candidate = mapping.mapping_candidate
        with st.container(border=True):
            left, right = st.columns((1.3, 1))
            left.markdown(f"**{mapping.display_name}**")
            left.caption(
                f"{mapping.cell_count} annotation cells · detection confidence: {candidate.confidence.value.upper()}"
            )
            labels = ", ".join(candidate.evidence.text_labels) or "No semantic text labels detected"
            colors = ", ".join(candidate.evidence.color_values) or "No semantic fill colors detected"
            right.markdown(f"**Text evidence:** {labels}  \n**Style evidence:** {colors}")
            issue = blocking_by_target.get(("annotation_mapping", mapping.rater_id))
            if issue is not None:
                options = [
                    "Choose coding...",
                    "Green = Metaphor; Red = Non-metaphor",
                    "Green = Non-metaphor; Red = Metaphor",
                ]
                if candidate.evidence.text_labels:
                    options.append("Use recognized text labels as primary evidence")
                choice = st.selectbox(
                    f"Confirm coding for {mapping.display_name}",
                    options,
                    key=f"mapping_decision_{mapping.rater_id}",
                )
                values = {
                    "Green = Metaphor; Red = Non-metaphor": "confirm_green_metaphor_red_non_metaphor",
                    "Green = Non-metaphor; Red = Metaphor": "green_non_metaphor_red_metaphor",
                    "Use recognized text labels as primary evidence": "use_labels",
                }
                if choice in values:
                    decisions.append(
                        _make_decision(
                            "annotation_mapping",
                            mapping.rater_id,
                            None,
                            values[choice],
                            "Researcher confirmed annotation coding in Data Validation.",
                        )
                    )
                else:
                    unresolved_controls += 1
            else:
                st.info(
                    "Recognized labels and cell-style evidence are internally consistent. Review the evidence above before validating the dataset.",
                    icon=":material/check_circle:",
                )

    if draft.normalization_proposals:
        st.markdown("#### Grammatical category normalization")
        st.caption("Proposals change only the validated layer. Original Excel values remain preserved.")
        for proposal in draft.normalization_proposals:
            if proposal.original not in active_categories:
                continue
            choice = st.selectbox(
                f"{proposal.original} → {proposal.proposed}",
                [
                    "Choose...",
                    f"Accept {proposal.proposed}",
                    f"Keep original: {proposal.original}",
                ],
                key=f"normalization_{proposal.original}",
            )
            if choice == f"Accept {proposal.proposed}":
                decisions.append(
                    _make_decision(
                        "category_normalization",
                        proposal.original,
                        proposal.original,
                        proposal.proposed,
                        proposal.reason,
                    )
                )
            elif choice == f"Keep original: {proposal.original}":
                decisions.append(
                    _make_decision(
                        "category_normalization",
                        proposal.original,
                        proposal.original,
                        "KEEP_ORIGINAL",
                        "Researcher chose to preserve the original category label.",
                    )
                )
            else:
                unresolved_controls += 1

    active_aggregate_candidates = tuple(
        candidate
        for candidate in draft.aggregate_candidates
        if candidate.aggregate_table_id in active_table_ids
    )
    if active_aggregate_candidates:
        st.markdown("#### Aggregate source detection")
        for candidate in active_aggregate_candidates:
            st.markdown(
                f"**{candidate.aggregate_source_title}** matches {candidate.matched_units} units "
                f"across component tables ({candidate.coverage:.0%} coverage)."
            )
            choice = st.selectbox(
                "How should this source be treated?",
                ["Choose...", "Treat as aggregate (recommended)", "Treat as independent source"],
                key=f"aggregate_{candidate.aggregate_table_id}",
            )
            if choice == "Treat as aggregate (recommended)":
                decisions.append(
                    _make_decision(
                        "aggregate_role",
                        candidate.aggregate_table_id,
                        None,
                        "aggregate",
                        "Researcher confirmed the detected combined source as an aggregate view.",
                    )
                )
            elif choice == "Treat as independent source":
                decisions.append(
                    _make_decision(
                        "aggregate_role",
                        candidate.aggregate_table_id,
                        None,
                        "independent",
                        "Researcher chose to treat the candidate as an independent source.",
                    )
                )
            else:
                unresolved_controls += 1

    st.markdown("#### Data-quality findings")
    relevant_issues = []
    for issue in draft.issues:
        if issue.decision_type == "worksheet_role":
            relevant_issues.append(issue)
        elif issue.decision_type == "annotation_mapping" or issue.target_id in {m.rater_id for m in draft.rater_mappings}:
            if issue.target_id in active_rater_ids:
                relevant_issues.append(issue)
        elif issue.decision_type == "aggregate_role":
            if issue.target_id in active_table_ids:
                relevant_issues.append(issue)
        elif issue.decision_type == "category_normalization":
            if issue.target_id in active_categories:
                relevant_issues.append(issue)
        else:
            relevant_issues.append(issue)
    if not relevant_issues:
        st.info("No validation issues were detected for the selected study-data worksheets.")
    else:
        for issue in relevant_issues:
            label = _issue_label(issue.severity)
            text = f"**{label}** · {issue.message}"
            if issue.severity == IssueSeverity.REQUIRES_ACTION:
                st.warning(text, icon=":material/rule:")
            elif issue.severity == IssueSeverity.WARNING:
                st.warning(text, icon=":material/warning:")
            else:
                st.info(text, icon=":material/info:")

    _render_provenance_inspector(draft, active_table_ids)
    _render_additional_raters(draft)

    st.divider()
    if unresolved_controls:
        st.caption(
            f"{unresolved_controls} validation decision(s) still require your confirmation."
        )
    validate_clicked = st.button(
        "Validate Dataset",
        type="primary",
        icon=":material/verified:",
        disabled=bool(unresolved_controls),
        use_container_width=True,
    )
    if validate_clicked:
        try:
            dataset = ValidationService().validate(draft, tuple(decisions))
            st.session_state[VALIDATED_DATASET_KEY] = dataset
            st.session_state[VALIDATION_DECISIONS_KEY] = list(decisions)
            st.session_state[DATASET_STATUS_KEY] = "validated"
            persist_validated_dataset_if_project(st.session_state, dataset)
            dataset = st.session_state.get(VALIDATED_DATASET_KEY, dataset)
            non_aggregate_sources = {
                source.source_id for source in dataset.sources if not source.is_aggregate
            }
            analytical_units = sum(
                unit.source_id in non_aggregate_sources for unit in dataset.units
            )
            st.info(
                f"Dataset validated: {analytical_units} analytical units and {len(dataset.raters)} raters are ready for analysis.",
                icon=":material/check_circle:",
            )
            st.rerun()
        except ValidationBlocked as exc:
            render_user_error(exc, context={"event_type": "validation_blocked"})

    if st.session_state.get(VALIDATED_DATASET_KEY) is not None:
        st.info(
            "Dataset validated. Open Annotations to inspect the canonical rater matrix.",
            icon=":material/verified:",
        )
