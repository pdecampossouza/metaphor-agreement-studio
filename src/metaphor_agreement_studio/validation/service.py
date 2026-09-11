from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from pathlib import Path

from metaphor_agreement_studio.common.errors import ValidationBlocked as BaseValidationBlocked
from metaphor_agreement_studio.domain.enums import (
    Classification,
    IssueSeverity,
    SourceType,
    ValidationStatus,
)
from metaphor_agreement_studio.domain.imports import (
    RaterMappingDraft,
    ValidationDecision,
    ValidationDraft,
    ValidatedDataset,
    WorkbookInspection,
)
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.import_engine.colors import color_family, resolve_fill_color
from metaphor_agreement_studio.import_engine.mappings import (
    classification_from_label,
    infer_annotation_mapping,
)
from metaphor_agreement_studio.import_engine.tables import detect_tables
from metaphor_agreement_studio.validation.aggregate import detect_aggregate_sources
from metaphor_agreement_studio.validation.issues import ValidationIssue
from metaphor_agreement_studio.validation.normalization import propose_category_normalizations


class ValidationBlocked(BaseValidationBlocked):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        details = "; ".join(issue.message for issue in issues)
        super().__init__(f"Validation blocked: {details}")


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:16]


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(
    code: str,
    severity: IssueSeverity,
    message: str,
    target_id: str | None = None,
    decision_type: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=_stable_id("issue_", code, target_id or "", message),
        code=code,
        severity=severity,
        message=message,
        target_id=target_id,
        decision_type=decision_type,
    )


class ValidationService:
    def prepare(
        self,
        inspection: WorkbookInspection,
        *,
        require_worksheet_roles: bool = True,
    ) -> ValidationDraft:
        tables = detect_tables(inspection)
        issues: list[ValidationIssue] = []
        if not tables:
            issues.append(
                _issue(
                    "no_annotation_tables",
                    IssueSeverity.REQUIRES_ACTION,
                    "No annotation tables could be detected in this workbook.",
                )
            )

        table_sheet_names = tuple(dict.fromkeys(table.sheet_name for table in tables))
        if require_worksheet_roles and len(table_sheet_names) > 1:
            for sheet_name in table_sheet_names:
                issues.append(
                    _issue(
                        "worksheet_role_decision",
                        IssueSeverity.REQUIRES_ACTION,
                        (
                            f"Choose how worksheet {sheet_name!r} should be used: "
                            "study data, synthetic/example data, or ignored."
                        ),
                        target_id=sheet_name,
                        decision_type="worksheet_role",
                    )
                )

        cells_by_rater: dict[str, list] = defaultdict(list)
        display_names: dict[str, str] = {}
        for table in tables:
            for rater_index, rater_column in enumerate(table.rater_columns):
                key = _norm(rater_column.display_name)
                display_names.setdefault(key, rater_column.display_name)
                cells_by_rater[key].extend(row.annotation_cells[rater_index] for row in table.rows)

        rater_mappings: list[RaterMappingDraft] = []
        for key in cells_by_rater:
            display_name = display_names[key]
            rater_id = _stable_id("rater_", key)
            candidate = infer_annotation_mapping(
                cells_by_rater[key], workbook_theme=inspection.workbook_theme
            )
            rater_mappings.append(
                RaterMappingDraft(
                    rater_id=rater_id,
                    display_name=display_name,
                    mapping_candidate=candidate,
                    cell_count=len(cells_by_rater[key]),
                )
            )
            for candidate_issue in candidate.issues:
                severity = candidate_issue.severity
                if candidate.confidence.value == "medium":
                    severity = IssueSeverity.WARNING
                issues.append(
                    _issue(
                        candidate_issue.code,
                        severity,
                        candidate_issue.message,
                        target_id=rater_id,
                        decision_type="annotation_mapping" if severity == IssueSeverity.REQUIRES_ACTION else None,
                    )
                )
            if candidate.confidence.value == "medium":
                issues.append(
                    _issue(
                        "confirm_annotation_mapping",
                        IssueSeverity.REQUIRES_ACTION,
                        f"Confirm the annotation mapping inferred from styles for rater {display_name}.",
                        target_id=rater_id,
                        decision_type="annotation_mapping",
                    )
                )

        category_labels = [row.grammatical_category for table in tables for row in table.rows]
        normalization_map = propose_category_normalizations(category_labels)
        normalization_proposals = tuple(normalization_map.values())
        for proposal in normalization_proposals:
            issues.append(
                _issue(
                    "category_normalization_decision",
                    IssueSeverity.REQUIRES_ACTION,
                    f"Review grammatical category normalization: {proposal.original!r} → {proposal.proposed!r}.",
                    target_id=proposal.original,
                    decision_type="category_normalization",
                )
            )

        aggregate_candidates = detect_aggregate_sources(tables)
        for aggregate in aggregate_candidates:
            issues.append(
                _issue(
                    "aggregate_role_decision",
                    IssueSeverity.REQUIRES_ACTION,
                    (
                        f"Confirm whether {aggregate.aggregate_source_title!r} is an aggregate source "
                        f"covering {aggregate.matched_units} analytical units."
                    ),
                    target_id=aggregate.aggregate_table_id,
                    decision_type="aggregate_role",
                )
            )

        return ValidationDraft(
            inspection=inspection,
            tables=tables,
            rater_mappings=tuple(rater_mappings),
            normalization_proposals=normalization_proposals,
            aggregate_candidates=aggregate_candidates,
            alignment_results=(),
            issues=tuple(issues),
        )

    def prepare_for_worksheet_roles(
        self,
        inspection: WorkbookInspection,
        worksheet_roles: dict[str, str],
    ) -> ValidationDraft:
        valid_roles = {"study_data", "synthetic_example", "ignore"}
        unknown_values = {value for value in worksheet_roles.values() if value not in valid_roles}
        if unknown_values:
            raise ValueError(f"Unknown worksheet role values: {sorted(unknown_values)}")
        study_sheet_names = {
            name for name, role in worksheet_roles.items() if role == "study_data"
        }
        filtered = replace(
            inspection,
            sheets=tuple(
                sheet for sheet in inspection.sheets if sheet.name in study_sheet_names
            ),
        )
        return self.prepare(filtered, require_worksheet_roles=False)

    def validate(
        self,
        draft: ValidationDraft,
        decisions: tuple[ValidationDecision, ...],
    ) -> ValidatedDataset:
        decision_index = {(item.decision_type, item.target_id): item for item in decisions}
        table_sheet_names = tuple(dict.fromkeys(table.sheet_name for table in draft.tables))
        worksheet_roles: dict[str, str] = {}
        if len(table_sheet_names) <= 1:
            worksheet_roles = {sheet_name: "study_data" for sheet_name in table_sheet_names}
        else:
            for sheet_name in table_sheet_names:
                decision = decision_index.get(("worksheet_role", sheet_name))
                if decision and decision.validated_value in {"study_data", "synthetic_example", "ignore"}:
                    worksheet_roles[sheet_name] = decision.validated_value

        active_tables = tuple(
            table
            for table in draft.tables
            if worksheet_roles.get(table.sheet_name) == "study_data"
        )
        mapping_by_id = {item.rater_id: item for item in draft.rater_mappings}
        rater_id_by_name = {_norm(item.display_name): item.rater_id for item in draft.rater_mappings}
        active_table_ids = {table.table_id for table in active_tables}
        active_rater_ids = {
            rater_id_by_name[_norm(rater.display_name)]
            for table in active_tables
            for rater in table.rater_columns
        }
        active_categories = {
            row.grammatical_category for table in active_tables for row in table.rows
        }

        def issue_is_relevant(issue: ValidationIssue) -> bool:
            if issue.decision_type == "worksheet_role":
                return True
            if issue.decision_type == "annotation_mapping":
                return (issue.target_id or "") in active_rater_ids
            if issue.decision_type == "aggregate_role":
                return (issue.target_id or "") in active_table_ids
            if issue.decision_type == "category_normalization":
                return (issue.target_id or "") in active_categories
            if issue.target_id in active_rater_ids:
                return True
            return issue.decision_type is None

        unresolved = tuple(
            issue
            for issue in draft.issues
            if issue.blocks_validation
            and issue_is_relevant(issue)
            and (
                issue.decision_type is None
                or (issue.decision_type, issue.target_id or "") not in decision_index
            )
        )
        if unresolved:
            raise ValidationBlocked(unresolved)
        if draft.tables and not active_tables:
            raise ValidationBlocked(
                (
                    _issue(
                        "no_study_data_worksheet",
                        IssueSeverity.REQUIRES_ACTION,
                        "At least one worksheet must be designated as Study data before validation.",
                        decision_type="worksheet_role",
                    ),
                )
            )

        normalization_by_original: dict[str, str] = {}
        for proposal in draft.normalization_proposals:
            decision = decision_index.get(("category_normalization", proposal.original))
            if decision and decision.validated_value:
                if decision.validated_value == "KEEP_ORIGINAL":
                    normalization_by_original[proposal.original] = proposal.original
                else:
                    normalization_by_original[proposal.original] = decision.validated_value

        aggregate_ids: set[str] = set()
        for candidate in draft.aggregate_candidates:
            decision = decision_index.get(("aggregate_role", candidate.aggregate_table_id))
            if decision and (decision.validated_value or "").casefold() == "aggregate":
                aggregate_ids.add(candidate.aggregate_table_id)

        import_hash = _file_hash(draft.inspection.path)
        import_id = "imp_" + import_hash[:16]
        sources: list[Source] = []
        units: list[LexicalUnit] = []
        annotations: list[Annotation] = []

        raters = tuple(
            Rater(
                rater_id=item.rater_id,
                display_name=item.display_name,
                source_file_id=import_id,
                metadata={"mapping_confidence": item.mapping_candidate.confidence.value},
            )
            for item in draft.rater_mappings
            if item.rater_id in active_rater_ids
        )

        for table in active_tables:
            is_aggregate = table.table_id in aggregate_ids
            sources.append(
                Source(
                    source_id=table.table_id,
                    display_name=table.source_title,
                    source_type=SourceType.AGGREGATE if is_aggregate else SourceType.TABLE,
                    is_aggregate=is_aggregate,
                )
            )
            occurrences: Counter[tuple[str, str]] = Counter()
            for row in table.rows:
                validated_pos = normalization_by_original.get(
                    row.grammatical_category, row.grammatical_category
                )
                lexical_value = unicodedata.normalize("NFKC", row.lexical_unit).strip()
                occurrence_key = (_norm(lexical_value), _norm(validated_pos))
                occurrences[occurrence_key] += 1
                occurrence_index = occurrences[occurrence_key]
                unit_id = _stable_id(
                    "unit_",
                    table.table_id,
                    occurrence_key[0],
                    occurrence_key[1],
                    occurrence_index,
                )
                units.append(
                    LexicalUnit(
                        unit_id=unit_id,
                        lexical_unit=lexical_value,
                        grammatical_category=validated_pos,
                        source_id=table.table_id,
                        occurrence_index=occurrence_index,
                    )
                )
                for rater_index, cell in enumerate(row.annotation_cells):
                    rater_column = table.rater_columns[rater_index]
                    rater_id = rater_id_by_name[_norm(rater_column.display_name)]
                    mapping_draft = mapping_by_id[rater_id]
                    decision = decision_index.get(("annotation_mapping", rater_id))
                    classification, method = self._classify(
                        cell,
                        mapping_draft,
                        draft.inspection.workbook_theme,
                        decision,
                    )
                    style = asdict(cell.fill)
                    style.update(
                        {
                            "style_id": cell.style_id,
                            "font_id": cell.font_id,
                            "border_id": cell.border_id,
                        }
                    )
                    annotation_id = _stable_id("ann_", unit_id, rater_id, import_id)
                    annotations.append(
                        Annotation(
                            annotation_id=annotation_id,
                            unit_id=unit_id,
                            rater_id=rater_id,
                            classification=classification,
                            import_id=import_id,
                            original_sheet=cell.sheet_name,
                            original_cell=cell.coordinate,
                            original_raw_value=cell.raw_value,
                            original_style=style,
                            detection_method=method,
                            validation_status=ValidationStatus.VALIDATED,
                        )
                    )

        dataset_id = _stable_id(
            "dataset_",
            import_hash,
            *(sorted(item.decision_id for item in decisions)),
        )
        return ValidatedDataset(
            dataset_id=dataset_id,
            sources=tuple(sources),
            units=tuple(units),
            raters=raters,
            annotations=tuple(annotations),
            quality_notes=tuple(issue for issue in draft.issues if issue_is_relevant(issue)),
            validation_decisions=decisions,
        )

    @staticmethod
    def _classify(cell, mapping_draft, workbook_theme, decision):
        candidate = mapping_draft.mapping_candidate
        resolved = resolve_fill_color(cell, workbook_theme)
        family = color_family(resolved.rgb)
        decision_value = (decision.validated_value if decision else "") or ""
        normalized_decision = decision_value.casefold()
        if normalized_decision == "green_non_metaphor_red_metaphor" and family in {"green", "red"}:
            reverse = {
                "green": Classification.NON_METAPHOR,
                "red": Classification.METAPHOR,
            }
            return reverse[family], f"validated reversed cell fill ({family})"
        prefer_color = normalized_decision in {
            "confirm_green_metaphor_red_non_metaphor",
            "use_colors",
        }
        if prefer_color and family in candidate.mapping.color_family_map:
            return candidate.mapping.color_family_map[family], f"validated cell fill ({family})"
        semantic = classification_from_label(cell.raw_value)
        if semantic is not None:
            return semantic, "recognized text/binary label"
        if family in candidate.mapping.color_family_map:
            return candidate.mapping.color_family_map[family], f"validated cell fill ({family})"
        return Classification.MISSING, "empty or unrecognized annotation"
