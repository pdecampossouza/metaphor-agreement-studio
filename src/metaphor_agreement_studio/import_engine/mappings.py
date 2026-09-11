from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from metaphor_agreement_studio.domain.enums import Classification, IssueSeverity
from metaphor_agreement_studio.domain.imports import (
    AnnotationMapping,
    CellSnapshot,
    ConfidenceLevel,
    ImportIssueCandidate,
    MappingCandidate,
    MappingEvidence,
)
from metaphor_agreement_studio.import_engine.colors import color_family, color_hex, resolve_fill_color

_POSITIVE = {"YES", "SIM", "M", "METAPHOR", "TRUE", "1"}
_NEGATIVE = {"NO", "NÃO", "NAO", "NM", "NON-METAPHOR", "NON METAPHOR", "FALSE", "0"}
_COLOR_PRIOR = {
    "green": Classification.METAPHOR,
    "red": Classification.NON_METAPHOR,
}


def normalize_annotation_label(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int) and value in (0, 1):
        return str(value)
    if isinstance(value, float) and value in (0.0, 1.0):
        return str(int(value))
    text = unicodedata.normalize("NFKC", str(value)).strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text or None


def classification_from_label(value: object) -> Classification | None:
    label = normalize_annotation_label(value)
    if label in _POSITIVE:
        return Classification.METAPHOR
    if label in _NEGATIVE:
        return Classification.NON_METAPHOR
    return None


def infer_annotation_mapping(
    cells: Iterable[CellSnapshot],
    workbook_theme: str | bytes | None = None,
) -> MappingCandidate:
    text_labels: set[str] = set()
    color_families: set[str] = set()
    color_values: set[str] = set()
    labeled_style_pairs: list[tuple[str, Classification]] = []

    for cell in cells:
        label = normalize_annotation_label(cell.raw_value)
        semantic = classification_from_label(cell.raw_value)
        if semantic is not None and label is not None:
            text_labels.add(label)
        resolved = resolve_fill_color(cell, workbook_theme)
        family = color_family(resolved.rgb)
        if family != "unknown" and resolved.rgb is not None:
            color_values.add(color_hex(resolved.rgb))
        if family in _COLOR_PRIOR:
            color_families.add(family)
            if semantic is not None:
                labeled_style_pairs.append((family, semantic))

    conflict = any(_COLOR_PRIOR[family] != semantic for family, semantic in labeled_style_pairs)
    has_labels = bool(text_labels)
    has_semantic_colors = bool(color_families)

    issues: list[ImportIssueCandidate] = []
    if conflict:
        confidence = ConfidenceLevel.LOW
        issues.append(
            ImportIssueCandidate(
                code="annotation_mapping_conflict",
                severity=IssueSeverity.REQUIRES_ACTION,
                message=(
                    "Annotation mapping conflict: recognized text labels disagree with the "
                    "green/red style evidence. Confirm the intended coding before validation."
                ),
            )
        )
    elif has_labels and has_semantic_colors:
        confidence = ConfidenceLevel.HIGH
    elif has_labels:
        confidence = ConfidenceLevel.HIGH
    elif has_semantic_colors:
        confidence = ConfidenceLevel.MEDIUM
        issues.append(
            ImportIssueCandidate(
                code="style_only_annotation_mapping",
                severity=IssueSeverity.WARNING,
                message="Annotation semantics were inferred from cell styles only and require researcher confirmation.",
            )
        )
    else:
        confidence = ConfidenceLevel.LOW
        issues.append(
            ImportIssueCandidate(
                code="annotation_mapping_unresolved",
                severity=IssueSeverity.REQUIRES_ACTION,
                message="No recognized annotation labels or semantic color styles were detected.",
            )
        )

    label_map = {label: Classification.METAPHOR for label in _POSITIVE}
    label_map.update({label: Classification.NON_METAPHOR for label in _NEGATIVE})
    mapping = AnnotationMapping.create(label_map=label_map, color_family_map=_COLOR_PRIOR)
    evidence = MappingEvidence(
        text_labels=tuple(sorted(text_labels)),
        color_families=tuple(sorted(color_families)),
        color_values=tuple(sorted(color_values)),
        labeled_style_pairs=tuple(labeled_style_pairs),
    )
    return MappingCandidate(evidence=evidence, mapping=mapping, confidence=confidence, issues=tuple(issues))


def classify_cell(
    cell: CellSnapshot,
    candidate: MappingCandidate,
    workbook_theme: str | bytes | None = None,
) -> tuple[Classification, str]:
    semantic = classification_from_label(cell.raw_value)
    if semantic is not None:
        return semantic, "recognized text/binary label"
    resolved = resolve_fill_color(cell, workbook_theme)
    family = color_family(resolved.rgb)
    if family in candidate.mapping.color_family_map:
        return candidate.mapping.color_family_map[family], f"cell fill ({family})"
    return Classification.MISSING, "empty or unrecognized annotation"
