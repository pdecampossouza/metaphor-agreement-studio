from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    project_id: str
    name: str
    created_at: str
    updated_at: str
    app_version: str


@dataclass(frozen=True, slots=True)
class DatasetVersionRecord:
    version_id: str
    ordinal: int
    created_at: str
    reason: str
    content_hash: str
    payload_json: str

    @property
    def display_id(self) -> str:
        return f"v{self.ordinal}.0"


@dataclass(frozen=True, slots=True)
class AnalysisVersionRecord:
    analysis_id: str
    ordinal: int
    dataset_version_id: str
    created_at: str
    config_json: str
    config_hash: str

    @property
    def display_id(self) -> str:
        return f"A-{self.ordinal:03d}"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    occurred_at: str
    event_type: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)
    dataset_version_id: str | None = None
    analysis_id: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    stored_relpath: str
    sha256: str
    created_at: str
    dataset_version_id: str
    analysis_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredSourceFile:
    file_id: str
    original_name: str
    stored_path: Path
    stored_relpath: str
    sha256: str
    byte_length: int
    imported_at: str


@dataclass(frozen=True, slots=True)
class ProjectContext:
    root: Path
    project: ProjectRecord
    current_dataset_version: DatasetVersionRecord | None = None
    current_analysis_version: AnalysisVersionRecord | None = None
    source_files: tuple[StoredSourceFile, ...] = ()
    dataset: Any | None = None
    audit_events: tuple[AuditEvent, ...] = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
