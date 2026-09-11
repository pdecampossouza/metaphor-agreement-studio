from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from metaphor_agreement_studio.domain.enums import Classification, IssueSeverity
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source

if TYPE_CHECKING:
    from metaphor_agreement_studio.validation.issues import ValidationIssue


@dataclass(frozen=True, slots=True)
class FillSnapshot:
    fill_type: str | None
    fg_type: str | None
    fg_rgb: str | None
    fg_indexed: int | None
    fg_theme: int | None
    fg_tint: float
    bg_type: str | None
    bg_rgb: str | None
    bg_indexed: int | None
    bg_theme: int | None
    bg_tint: float


@dataclass(frozen=True, slots=True)
class CellSnapshot:
    workbook_path: Path
    sheet_name: str
    coordinate: str
    row: int
    column: int
    raw_value: Any
    fill: FillSnapshot
    style_id: int | None
    font_id: int | None
    border_id: int | None
    number_format: str | None


@dataclass(frozen=True, slots=True)
class SheetSnapshot:
    name: str
    cells: tuple[CellSnapshot, ...]
    max_row: int
    max_column: int
    merged_ranges: tuple[str, ...]

    def cell(self, coordinate: str) -> CellSnapshot:
        target = coordinate.upper()
        for cell in self.cells:
            if cell.coordinate.upper() == target:
                return cell
        raise KeyError(f"Cell {coordinate!r} not found in sheet {self.name!r}")

    def iter_cells(self) -> Iterable[CellSnapshot]:
        return iter(self.cells)

    def cells_in_range(self, cell_range: str) -> tuple[CellSnapshot, ...]:
        from openpyxl.utils.cell import range_boundaries

        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
        return tuple(
            cell
            for cell in self.cells
            if min_row <= cell.row <= max_row and min_col <= cell.column <= max_col
        )


@dataclass(frozen=True, slots=True)
class WorkbookInspection:
    path: Path
    sheets: tuple[SheetSnapshot, ...]
    workbook_theme: str | None = None

    @property
    def sheet_names(self) -> tuple[str, ...]:
        return tuple(sheet.name for sheet in self.sheets)

    def sheet(self, name: str) -> SheetSnapshot:
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        raise KeyError(f"Sheet {name!r} not found")

    def annotation_cells(self, sheet_name: str, cell_range: str) -> tuple[CellSnapshot, ...]:
        return self.sheet(sheet_name).cells_in_range(cell_range)


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class ImportIssueCandidate:
    code: str
    severity: IssueSeverity
    message: str
    target_id: str | None = None


@dataclass(frozen=True, slots=True)
class MappingEvidence:
    text_labels: tuple[str, ...]
    color_families: tuple[str, ...]
    color_values: tuple[str, ...]
    labeled_style_pairs: tuple[tuple[str, Classification], ...]


@dataclass(frozen=True, slots=True)
class AnnotationMapping:
    semantic_positive: Classification
    semantic_negative: Classification
    label_map: Mapping[str, Classification]
    color_family_map: Mapping[str, Classification]

    @classmethod
    def create(
        cls,
        label_map: Mapping[str, Classification],
        color_family_map: Mapping[str, Classification],
    ) -> "AnnotationMapping":
        return cls(
            semantic_positive=Classification.METAPHOR,
            semantic_negative=Classification.NON_METAPHOR,
            label_map=MappingProxyType(dict(label_map)),
            color_family_map=MappingProxyType(dict(color_family_map)),
        )


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    evidence: MappingEvidence
    mapping: AnnotationMapping
    confidence: ConfidenceLevel
    issues: tuple[ImportIssueCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class RaterColumnCandidate:
    display_name: str
    column: int
    name_cell: str
    header_cell: str
    question_header: str


@dataclass(frozen=True, slots=True)
class TableRowCandidate:
    row: int
    order: int
    lexical_unit: str
    grammatical_category: str
    annotation_cells: tuple[CellSnapshot, ...]


@dataclass(frozen=True, slots=True)
class TableCandidate:
    table_id: str
    workbook_path: Path
    sheet_name: str
    source_title: str
    title_cell: str | None
    header_row: int
    data_start_row: int
    data_end_row: int
    first_column: int
    last_column: int
    order_column: int
    lexical_unit_column: int
    grammatical_category_column: int
    rater_columns: tuple[RaterColumnCandidate, ...]
    rows: tuple[TableRowCandidate, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class AggregateCandidate:
    aggregate_table_id: str
    aggregate_source_title: str
    component_table_ids: tuple[str, ...]
    matched_units: int
    coverage: float


class AlignmentStatus(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class NormalizationProposal:
    original: str
    proposed: str
    reason: str
    confidence: ConfidenceLevel


@dataclass(frozen=True, slots=True)
class AlignmentUnit:
    unit_id: str
    source_identity: str
    lexical_unit: str
    grammatical_category: str
    occurrence_index: int


@dataclass(frozen=True, slots=True)
class AlignmentMatch:
    incoming: AlignmentUnit
    reference: AlignmentUnit | None
    status: AlignmentStatus
    similarity: float
    accepted: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    matches: tuple[AlignmentMatch, ...]

    @property
    def exact(self) -> tuple[AlignmentMatch, ...]:
        return tuple(item for item in self.matches if item.status == AlignmentStatus.EXACT)

    @property
    def probable(self) -> tuple[AlignmentMatch, ...]:
        return tuple(item for item in self.matches if item.status == AlignmentStatus.PROBABLE)

    @property
    def no_match(self) -> tuple[AlignmentMatch, ...]:
        return tuple(item for item in self.matches if item.status == AlignmentStatus.NO_MATCH)


@dataclass(frozen=True, slots=True)
class RaterMappingDraft:
    rater_id: str
    display_name: str
    mapping_candidate: MappingCandidate
    cell_count: int


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    decision_id: str
    decision_type: str
    target_id: str
    original_value: str | None
    validated_value: str | None
    reason: str
    decided_at: str
    actor: str = "Researcher"


@dataclass(frozen=True, slots=True)
class ValidationDraft:
    inspection: WorkbookInspection
    tables: tuple[TableCandidate, ...]
    rater_mappings: tuple[RaterMappingDraft, ...]
    normalization_proposals: tuple[NormalizationProposal, ...]
    aggregate_candidates: tuple[AggregateCandidate, ...]
    alignment_results: tuple[AlignmentResult, ...]
    issues: tuple["ValidationIssue", ...]


@dataclass(frozen=True, slots=True)
class ValidatedDataset:
    dataset_id: str
    sources: tuple[Source, ...]
    units: tuple[LexicalUnit, ...]
    raters: tuple[Rater, ...]
    annotations: tuple[Annotation, ...]
    quality_notes: tuple["ValidationIssue", ...]
    validation_decisions: tuple[ValidationDecision, ...]

@dataclass(frozen=True, slots=True)
class UploadedWorkbook:
    local_path: Path
    original_display_name: str
    byte_length: int
    sha256: str
    role: str = "unassigned"
