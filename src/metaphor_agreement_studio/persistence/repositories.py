from __future__ import annotations

import json
import sqlite3

from metaphor_agreement_studio.persistence.types import (
    AnalysisVersionRecord,
    AuditEvent,
    ArtifactRecord,
    DatasetVersionRecord,
    ProjectRecord,
)


class DatasetVersionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def by_hash(self, content_hash: str) -> DatasetVersionRecord | None:
        row = self.conn.execute(
            "SELECT * FROM dataset_versions WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return _dataset_record(row) if row else None

    def latest(self) -> DatasetVersionRecord | None:
        row = self.conn.execute(
            "SELECT * FROM dataset_versions ORDER BY ordinal DESC LIMIT 1"
        ).fetchone()
        return _dataset_record(row) if row else None

    def insert(self, record: DatasetVersionRecord) -> None:
        self.conn.execute(
            """INSERT INTO dataset_versions
               (version_id, ordinal, created_at, reason, content_hash, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record.version_id,
                record.ordinal,
                record.created_at,
                record.reason,
                record.content_hash,
                record.payload_json,
            ),
        )
        self.conn.commit()


class AnalysisVersionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def by_dataset_and_hash(
        self, dataset_version_id: str, config_hash: str
    ) -> AnalysisVersionRecord | None:
        row = self.conn.execute(
            """SELECT * FROM analysis_versions
               WHERE dataset_version_id = ? AND config_hash = ?
               ORDER BY ordinal DESC LIMIT 1""",
            (dataset_version_id, config_hash),
        ).fetchone()
        return _analysis_record(row) if row else None

    def latest(self) -> AnalysisVersionRecord | None:
        row = self.conn.execute(
            "SELECT * FROM analysis_versions ORDER BY ordinal DESC LIMIT 1"
        ).fetchone()
        return _analysis_record(row) if row else None

    def insert(self, record: AnalysisVersionRecord) -> None:
        self.conn.execute(
            """INSERT INTO analysis_versions
               (analysis_id, ordinal, dataset_version_id, created_at, config_json, config_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record.analysis_id,
                record.ordinal,
                record.dataset_version_id,
                record.created_at,
                record.config_json,
                record.config_hash,
            ),
        )
        self.conn.commit()


class AuditRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, event: AuditEvent) -> None:
        self.conn.execute(
            """INSERT INTO audit_events
               (event_id, occurred_at, event_type, summary, details_json, dataset_version_id, analysis_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.occurred_at,
                event.event_type,
                event.summary,
                json.dumps(dict(event.details), ensure_ascii=False, sort_keys=True),
                event.dataset_version_id,
                event.analysis_id,
            ),
        )
        self.conn.commit()

    def list_newest_first(self) -> tuple[AuditEvent, ...]:
        rows = self.conn.execute(
            "SELECT * FROM audit_events ORDER BY occurred_at DESC, rowid DESC"
        ).fetchall()
        return tuple(
            AuditEvent(
                event_id=row["event_id"],
                occurred_at=row["occurred_at"],
                event_type=row["event_type"],
                summary=row["summary"],
                details=json.loads(row["details_json"]),
                dataset_version_id=row["dataset_version_id"],
                analysis_id=row["analysis_id"],
            )
            for row in rows
        )


class ArtifactRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, record: ArtifactRecord) -> None:
        self.conn.execute(
            """INSERT INTO artifacts
               (artifact_id, kind, stored_relpath, sha256, created_at, dataset_version_id, analysis_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.artifact_id, record.kind, record.stored_relpath, record.sha256, record.created_at,
                record.dataset_version_id, record.analysis_id,
                json.dumps(dict(record.metadata), ensure_ascii=False, sort_keys=True),
            ),
        )
        self.conn.commit()

    def list_newest_first(self) -> tuple[ArtifactRecord, ...]:
        rows = self.conn.execute(
            "SELECT * FROM artifacts ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
        return tuple(
            ArtifactRecord(
                artifact_id=row["artifact_id"],
                kind=row["kind"],
                stored_relpath=row["stored_relpath"],
                sha256=row["sha256"],
                created_at=row["created_at"],
                dataset_version_id=row["dataset_version_id"],
                analysis_id=row["analysis_id"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        )


def _dataset_record(row: sqlite3.Row) -> DatasetVersionRecord:
    return DatasetVersionRecord(
        version_id=row["version_id"],
        ordinal=row["ordinal"],
        created_at=row["created_at"],
        reason=row["reason"],
        content_hash=row["content_hash"],
        payload_json=row["payload_json"],
    )


def _analysis_record(row: sqlite3.Row) -> AnalysisVersionRecord:
    return AnalysisVersionRecord(
        analysis_id=row["analysis_id"],
        ordinal=row["ordinal"],
        dataset_version_id=row["dataset_version_id"],
        created_at=row["created_at"],
        config_json=row["config_json"],
        config_hash=row["config_hash"],
    )


def project_record_from_row(row: sqlite3.Row) -> ProjectRecord:
    return ProjectRecord(
        project_id=row["project_id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        app_version=row["app_version"],
    )
