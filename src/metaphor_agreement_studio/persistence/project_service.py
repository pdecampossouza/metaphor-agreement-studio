from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from metaphor_agreement_studio import __version__
from metaphor_agreement_studio.domain.enums import Classification, SourceType, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset, ValidationDecision
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.persistence.db import initialize_database, managed_database, transaction
from metaphor_agreement_studio.persistence.repositories import (
    AnalysisVersionRepository,
    ArtifactRepository,
    AuditRepository,
    DatasetVersionRepository,
    project_record_from_row,
)
from metaphor_agreement_studio.persistence.source_files import store_source_file
from metaphor_agreement_studio.persistence.types import ArtifactRecord, AuditEvent, ProjectContext, ProjectRecord, StoredSourceFile
from metaphor_agreement_studio.persistence.versioning import AnalysisVersionService, DatasetVersionService

PROJECT_DIRECTORIES = (
    "source_files",
    "exports/tables",
    "exports/figures",
    "exports/latex",
    "exports/datasets",
    "exports/artifacts",
    "reports",
    "backups",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(event_type: str, summary: str, *, details=None, dataset_version_id=None, analysis_id=None) -> AuditEvent:
    return AuditEvent(
        event_id=f"event_{uuid.uuid4().hex}",
        occurred_at=_now_iso(),
        event_type=event_type,
        summary=summary,
        details=details or {},
        dataset_version_id=dataset_version_id,
        analysis_id=analysis_id,
    )


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)



def _clear_current_dataset(conn) -> None:
    with transaction(conn):
        conn.execute("DELETE FROM validated_annotations")
        conn.execute("DELETE FROM raw_annotations")
        conn.execute("DELETE FROM validation_decisions")
        conn.execute("DELETE FROM lexical_units")
        conn.execute("DELETE FROM raters")
        conn.execute("DELETE FROM sources")
        conn.execute("DELETE FROM imports")

def _write_current_dataset(conn, dataset: ValidatedDataset, stored_files: tuple[StoredSourceFile, ...]) -> None:
    import_ids = sorted({annotation.import_id for annotation in dataset.annotations})
    if import_ids and not stored_files:
        raise ValueError("A persistent project with annotations requires at least one source workbook.")
    default_file_id = stored_files[0].file_id if stored_files else None

    with transaction(conn):
        for import_id in import_ids:
            conn.execute(
                """INSERT OR REPLACE INTO imports
                   (import_id, file_id, inspected_at, validation_status, raw_payload_json, detection_summary_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    import_id,
                    default_file_id,
                    _now_iso(),
                    "validated",
                    _json({"import_id": import_id, "preserved_in": "normalized project tables"}),
                    _json({"status": "validated", "source_file_count": len(stored_files)}),
                ),
            )

        for source in dataset.sources:
            conn.execute(
                """INSERT OR REPLACE INTO sources
                   (source_id, display_name, source_type, parent_source_id, is_aggregate)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    source.source_id,
                    source.display_name,
                    source.source_type.value,
                    source.parent_source_id,
                    int(source.is_aggregate),
                ),
            )

        for rater in dataset.raters:
            metadata = dict(rater.metadata)
            metadata["_original_source_file_id"] = rater.source_file_id
            conn.execute(
                """INSERT OR REPLACE INTO raters
                   (rater_id, display_name, source_file_id, metadata_json)
                   VALUES (?, ?, ?, ?)""",
                (rater.rater_id, rater.display_name, None, _json(metadata)),
            )

        for unit in dataset.units:
            conn.execute(
                """INSERT OR REPLACE INTO lexical_units
                   (unit_id, lexical_unit, grammatical_category, source_id, occurrence_index,
                    song, artist, verse, context, timestamp, source_metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')""",
                (
                    unit.unit_id,
                    unit.lexical_unit,
                    unit.grammatical_category,
                    unit.source_id,
                    unit.occurrence_index,
                    unit.song,
                    unit.artist,
                    unit.verse,
                    unit.context,
                    unit.timestamp,
                ),
            )

        for decision in dataset.validation_decisions:
            conn.execute(
                """INSERT OR REPLACE INTO validation_decisions
                   (decision_id, decision_type, target_id, original_value, validated_value, reason, decided_at, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.decision_id,
                    decision.decision_type,
                    decision.target_id,
                    decision.original_value,
                    decision.validated_value,
                    decision.reason,
                    decision.decided_at,
                    decision.actor,
                ),
            )

        for annotation in dataset.annotations:
            conn.execute(
                """INSERT OR REPLACE INTO raw_annotations
                   (annotation_id, unit_id, rater_id, import_id, original_sheet, original_cell,
                    original_raw_value_json, original_style_json, detection_method)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation.annotation_id,
                    annotation.unit_id,
                    annotation.rater_id,
                    annotation.import_id,
                    annotation.original_sheet,
                    annotation.original_cell,
                    _json(annotation.original_raw_value),
                    _json(dict(annotation.original_style)),
                    annotation.detection_method,
                ),
            )
            conn.execute(
                """INSERT OR REPLACE INTO validated_annotations
                   (annotation_id, classification, validated_at) VALUES (?, ?, ?)""",
                (annotation.annotation_id, annotation.classification.value, _now_iso()),
            )


def _load_dataset(conn, version_id: str) -> ValidatedDataset:
    sources = tuple(
        Source(
            source_id=row["source_id"],
            display_name=row["display_name"],
            source_type=SourceType(row["source_type"]),
            parent_source_id=row["parent_source_id"],
            is_aggregate=bool(row["is_aggregate"]),
        )
        for row in conn.execute("SELECT * FROM sources ORDER BY rowid")
    )
    units = tuple(
        LexicalUnit(
            unit_id=row["unit_id"],
            lexical_unit=row["lexical_unit"],
            grammatical_category=row["grammatical_category"],
            source_id=row["source_id"],
            occurrence_index=row["occurrence_index"],
            song=row["song"],
            artist=row["artist"],
            verse=row["verse"],
            context=row["context"],
            timestamp=row["timestamp"],
        )
        for row in conn.execute("SELECT * FROM lexical_units ORDER BY rowid")
    )
    raters = []
    for row in conn.execute("SELECT * FROM raters ORDER BY rowid"):
        metadata = json.loads(row["metadata_json"])
        original_source_file_id = metadata.pop("_original_source_file_id", row["source_file_id"])
        raters.append(
            Rater(
                rater_id=row["rater_id"],
                display_name=row["display_name"],
                source_file_id=original_source_file_id,
                metadata=metadata,
            )
        )
    annotations = []
    query = """
        SELECT raw.*, val.classification
        FROM raw_annotations raw
        JOIN validated_annotations val USING (annotation_id)
        ORDER BY raw.rowid
    """
    for row in conn.execute(query):
        raw_value = json.loads(row["original_raw_value_json"])
        style = json.loads(row["original_style_json"])
        annotations.append(
            Annotation(
                annotation_id=row["annotation_id"],
                unit_id=row["unit_id"],
                rater_id=row["rater_id"],
                classification=Classification(row["classification"]),
                import_id=row["import_id"],
                original_sheet=row["original_sheet"],
                original_cell=row["original_cell"],
                original_raw_value=raw_value,
                original_style=style,
                detection_method=row["detection_method"],
                validation_status=ValidationStatus.VALIDATED,
            )
        )
    decisions = tuple(
        ValidationDecision(
            decision_id=row["decision_id"],
            decision_type=row["decision_type"],
            target_id=row["target_id"],
            original_value=row["original_value"],
            validated_value=row["validated_value"],
            reason=row["reason"],
            decided_at=row["decided_at"],
            actor=row["actor"],
        )
        for row in conn.execute("SELECT * FROM validation_decisions ORDER BY rowid")
    )
    return ValidatedDataset(
        dataset_id=version_id,
        sources=sources,
        units=units,
        raters=tuple(raters),
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=decisions,
    )


def create_project(root: Path, name: str, session_dataset: ValidatedDataset, source_paths) -> ProjectContext:
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for relative in PROJECT_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)
    db_path = root / "project.db"
    initialize_database(db_path)
    project_id = f"project_{uuid.uuid4().hex}"
    now = _now_iso()
    project = ProjectRecord(project_id, name.strip() or "Untitled Study", now, now, __version__)

    stored_files = tuple(store_source_file(Path(path), root) for path in source_paths)
    with managed_database(db_path) as conn:
        with transaction(conn):
            conn.execute(
                "INSERT INTO project (project_id, name, created_at, updated_at, app_version) VALUES (?, ?, ?, ?, ?)",
                (project.project_id, project.name, project.created_at, project.updated_at, project.app_version),
            )
            for item in stored_files:
                conn.execute(
                    """INSERT OR IGNORE INTO source_files
                       (file_id, original_name, stored_relpath, sha256, byte_length, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        item.file_id,
                        item.original_name,
                        item.stored_relpath,
                        item.sha256,
                        item.byte_length,
                        item.imported_at,
                    ),
                )
        audit = AuditRepository(conn)
        audit.add(_event("project_created", f"Research project created: {project.name}"))
        for item in stored_files:
            audit.add(
                _event(
                    "source_file_added",
                    f"Source workbook preserved: {item.original_name}",
                    details={"sha256": item.sha256, "byte_length": item.byte_length},
                )
            )
        _write_current_dataset(conn, session_dataset, stored_files)
        dataset_version = DatasetVersionService(conn).create_if_changed(
            session_dataset, "Quick Analysis converted to Research Project"
        )
        audit.add(
            _event(
                "dataset_saved",
                f"Validated dataset saved as {dataset_version.display_id}",
                dataset_version_id=dataset_version.version_id,
                details={"content_hash": dataset_version.content_hash},
            )
        )
        audit.add(
            _event(
                "quick_analysis_saved_as_project",
                "Quick Analysis saved as a persistent Research Project",
                dataset_version_id=dataset_version.version_id,
            )
        )

    identity = {
        "project_id": project.project_id,
        "name": project.name,
        "app_version": project.app_version,
        "created_at": project.created_at,
    }
    (root / "project.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return open_project(root)


def open_project(root: Path) -> ProjectContext:
    root = Path(root).expanduser().resolve(strict=True)
    db_path = root / "project.db"
    if not db_path.is_file() or not (root / "project.json").is_file():
        raise ValueError("The selected folder is not a Metaphor Agreement Studio project.")
    initialize_database(db_path)
    with managed_database(db_path) as conn:
        project_row = conn.execute("SELECT * FROM project LIMIT 1").fetchone()
        if project_row is None:
            raise ValueError("Project metadata is missing from project.db.")
        project = project_record_from_row(project_row)
        dataset_version = DatasetVersionRepository(conn).latest()
        analysis_version = AnalysisVersionRepository(conn).latest()
        dataset = _load_dataset(conn, dataset_version.version_id) if dataset_version else None
        stored_files = tuple(
            StoredSourceFile(
                file_id=row["file_id"],
                original_name=row["original_name"],
                stored_path=root / row["stored_relpath"],
                stored_relpath=row["stored_relpath"],
                sha256=row["sha256"],
                byte_length=row["byte_length"],
                imported_at=row["imported_at"],
            )
            for row in conn.execute("SELECT * FROM source_files ORDER BY imported_at, rowid")
        )
        audit_events = AuditRepository(conn).list_newest_first()
        artifacts = ArtifactRepository(conn).list_newest_first()
    return ProjectContext(
        root=root,
        project=project,
        current_dataset_version=dataset_version,
        current_analysis_version=analysis_version,
        source_files=stored_files,
        dataset=dataset,
        audit_events=audit_events,
        artifacts=artifacts,
    )


def save_dataset_version(
    context: ProjectContext,
    dataset: ValidatedDataset,
    reason: str,
    source_paths=(),
) -> ProjectContext:
    existing_hashes = {item.sha256 for item in context.source_files}
    added_files = []
    for path in source_paths:
        stored = store_source_file(Path(path), context.root)
        if stored.sha256 not in existing_hashes:
            added_files.append(stored)
            existing_hashes.add(stored.sha256)
    all_files_by_hash = {item.sha256: item for item in context.source_files}
    all_files_by_hash.update({item.sha256: item for item in added_files})
    all_files = tuple(all_files_by_hash.values())

    with managed_database(context.root / "project.db") as conn:
        audit = AuditRepository(conn)
        with transaction(conn):
            for item in added_files:
                conn.execute(
                    """INSERT OR IGNORE INTO source_files
                       (file_id, original_name, stored_relpath, sha256, byte_length, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        item.file_id,
                        item.original_name,
                        item.stored_relpath,
                        item.sha256,
                        item.byte_length,
                        item.imported_at,
                    ),
                )
        for item in added_files:
            audit.add(
                _event(
                    "source_file_added",
                    f"Source workbook preserved: {item.original_name}",
                    details={"sha256": item.sha256, "byte_length": item.byte_length},
                )
            )

        before = DatasetVersionRepository(conn).latest()
        _clear_current_dataset(conn)
        _write_current_dataset(conn, dataset, all_files)
        version = DatasetVersionService(conn).create_if_changed(dataset, reason)
        if before is None or version.version_id != before.version_id:
            audit.add(
                _event(
                    "dataset_saved",
                    f"Validated dataset saved as {version.display_id}",
                    details={"reason": reason, "content_hash": version.content_hash},
                    dataset_version_id=version.version_id,
                )
            )
    return open_project(context.root)


def record_analysis_version(context: ProjectContext, config) -> ProjectContext:
    with managed_database(context.root / "project.db") as conn:
        dataset_version = DatasetVersionRepository(conn).latest()
        if dataset_version is None:
            raise ValueError("A validated dataset version is required before recording analysis settings.")
        previous = AnalysisVersionRepository(conn).latest()
        analysis = AnalysisVersionService(conn).record(dataset_version, config)
        if previous is None or analysis.analysis_id != previous.analysis_id:
            AuditRepository(conn).add(
                _event(
                    "analysis_recorded",
                    f"Analysis configuration recorded as {analysis.display_id}",
                    details={"config_hash": analysis.config_hash},
                    dataset_version_id=dataset_version.version_id,
                    analysis_id=analysis.analysis_id,
                )
            )
    return open_project(context.root)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_artifact(
    context: ProjectContext,
    artifact_path: Path,
    kind: str,
    metadata=None,
) -> ProjectContext:
    source = Path(artifact_path).expanduser().resolve(strict=True)
    if context.current_dataset_version is None:
        raise ValueError("A validated dataset version is required before registering artifacts.")
    target_dir = context.root / "exports" / "artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = f"artifact_{uuid.uuid4().hex}"
    target = target_dir / f"{artifact_id[:18]}_{source.name}"
    shutil.copy2(source, target)
    record = ArtifactRecord(
        artifact_id=artifact_id,
        kind=kind,
        stored_relpath=target.relative_to(context.root).as_posix(),
        sha256=_sha256_file(target),
        created_at=_now_iso(),
        dataset_version_id=context.current_dataset_version.version_id,
        analysis_id=context.current_analysis_version.analysis_id if context.current_analysis_version else None,
        metadata=metadata or {},
    )
    with managed_database(context.root / "project.db") as conn:
        ArtifactRepository(conn).insert(record)
        AuditRepository(conn).add(
            _event(
                "artifact_generated",
                f"Research artifact generated: {source.name}",
                details={"kind": kind, "sha256": record.sha256, **dict(record.metadata)},
                dataset_version_id=record.dataset_version_id,
                analysis_id=record.analysis_id,
            )
        )
    return open_project(context.root)
