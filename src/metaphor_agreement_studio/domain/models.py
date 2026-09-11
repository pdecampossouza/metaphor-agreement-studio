from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .enums import Classification, SourceType, ValidationStatus


@dataclass(frozen=True, slots=True)
class Source:
    source_id: str
    display_name: str
    source_type: SourceType = SourceType.TABLE
    parent_source_id: str | None = None
    is_aggregate: bool = False


@dataclass(frozen=True, slots=True)
class Rater:
    rater_id: str
    display_name: str
    source_file_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LexicalUnit:
    unit_id: str
    lexical_unit: str
    grammatical_category: str
    source_id: str
    occurrence_index: int
    song: str | None = None
    artist: str | None = None
    verse: str | None = None
    context: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class Annotation:
    annotation_id: str
    unit_id: str
    rater_id: str
    classification: Classification
    import_id: str
    original_sheet: str
    original_cell: str
    original_raw_value: Any
    original_style: Mapping[str, Any]
    detection_method: str
    validation_status: ValidationStatus


@dataclass(frozen=True, slots=True)
class WorkbookCandidate:
    path: Path
    display_name: str
    discovery_root: Path
