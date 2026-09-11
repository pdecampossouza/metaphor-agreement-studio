from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import sqlite3
from typing import Any, Mapping

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.persistence.repositories import (
    AnalysisVersionRepository,
    DatasetVersionRepository,
)
from metaphor_agreement_studio.persistence.types import (
    AnalysisVersionRecord,
    ArtifactRecord,
    DatasetVersionRecord,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_normalize(item) for item in value]
    if hasattr(value, "as_posix"):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _stable_json(payload: Any) -> str:
    return json.dumps(_normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_dataset_payload(dataset: ValidatedDataset) -> dict[str, Any]:
    return {
        "sources": [
            {
                "source_id": source.source_id,
                "display_name": source.display_name,
                "source_type": source.source_type.value,
                "parent_source_id": source.parent_source_id,
                "is_aggregate": source.is_aggregate,
            }
            for source in sorted(dataset.sources, key=lambda item: item.source_id)
        ],
        "units": [
            {
                "unit_id": unit.unit_id,
                "lexical_unit": unit.lexical_unit,
                "grammatical_category": unit.grammatical_category,
                "source_id": unit.source_id,
                "occurrence_index": unit.occurrence_index,
                "song": unit.song,
                "artist": unit.artist,
                "verse": unit.verse,
                "context": unit.context,
                "timestamp": unit.timestamp,
            }
            for unit in sorted(dataset.units, key=lambda item: item.unit_id)
        ],
        "raters": [
            {
                "rater_id": rater.rater_id,
                "display_name": rater.display_name,
                "source_file_id": rater.source_file_id,
                "metadata": _normalize(rater.metadata),
            }
            for rater in sorted(dataset.raters, key=lambda item: item.rater_id)
        ],
        "annotations": [
            {
                "annotation_id": annotation.annotation_id,
                "unit_id": annotation.unit_id,
                "rater_id": annotation.rater_id,
                "classification": annotation.classification.value,
            }
            for annotation in sorted(dataset.annotations, key=lambda item: item.annotation_id)
        ],
        "validation_decisions": [
            {
                "decision_id": decision.decision_id,
                "decision_type": decision.decision_type,
                "target_id": decision.target_id,
                "original_value": decision.original_value,
                "validated_value": decision.validated_value,
                "reason": decision.reason,
                "actor": decision.actor,
            }
            for decision in sorted(dataset.validation_decisions, key=lambda item: item.decision_id)
        ],
    }


def canonical_analysis_config(config: Any) -> dict[str, Any]:
    normalized = _normalize(config)
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


class DatasetVersionService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = DatasetVersionRepository(conn)

    def create_if_changed(self, dataset: ValidatedDataset, reason: str) -> DatasetVersionRecord:
        payload_json = _stable_json(canonical_dataset_payload(dataset))
        content_hash = _sha256_text(payload_json)
        existing = self.repo.by_hash(content_hash)
        if existing is not None:
            return existing
        latest = self.repo.latest()
        ordinal = 1 if latest is None else latest.ordinal + 1
        record = DatasetVersionRecord(
            version_id=f"dataset_{content_hash[:20]}",
            ordinal=ordinal,
            created_at=_now_iso(),
            reason=reason,
            content_hash=content_hash,
            payload_json=payload_json,
        )
        self.repo.insert(record)
        return record


class AnalysisVersionService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = AnalysisVersionRepository(conn)

    def record(self, dataset_version: DatasetVersionRecord, config: Any) -> AnalysisVersionRecord:
        config_json = _stable_json(canonical_analysis_config(config))
        config_hash = _sha256_text(config_json)
        existing = self.repo.by_dataset_and_hash(dataset_version.version_id, config_hash)
        if existing is not None:
            return existing
        latest = self.repo.latest()
        ordinal = 1 if latest is None else latest.ordinal + 1
        record = AnalysisVersionRecord(
            analysis_id=f"analysis_{ordinal:03d}_{config_hash[:12]}",
            ordinal=ordinal,
            dataset_version_id=dataset_version.version_id,
            created_at=_now_iso(),
            config_json=config_json,
            config_hash=config_hash,
        )
        self.repo.insert(record)
        return record


def artifact_is_current(
    artifact: ArtifactRecord,
    current_dataset_version: DatasetVersionRecord | str | None,
    current_analysis_version: AnalysisVersionRecord | str | None,
) -> bool:
    dataset_id = (
        current_dataset_version.version_id
        if isinstance(current_dataset_version, DatasetVersionRecord)
        else current_dataset_version
    )
    analysis_id = (
        current_analysis_version.analysis_id
        if isinstance(current_analysis_version, AnalysisVersionRecord)
        else current_analysis_version
    )
    if artifact.dataset_version_id != dataset_id:
        return False
    if artifact.analysis_id is None:
        return True
    return artifact.analysis_id == analysis_id
