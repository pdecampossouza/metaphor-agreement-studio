from __future__ import annotations

import hashlib
import json
from pathlib import Path

from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.persistence.versioning import (
    canonical_analysis_config,
    canonical_dataset_payload,
)

WORKBOOK_PARSER_VERSION = "workbook-parser-v1"
ANALYSIS_ENGINE_VERSION = "analysis-engine-v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def workbook_content_cache_key(path: Path, parser_version: str = WORKBOOK_PARSER_VERSION) -> str:
    resolved = Path(path).expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _sha256_bytes(f"{parser_version}:{digest.hexdigest()}".encode("utf-8"))


def dataset_content_hash(dataset: ValidatedDataset) -> str:
    return _sha256_bytes(_stable_json(canonical_dataset_payload(dataset)).encode("utf-8"))


def analysis_config_hash(config: object) -> str:
    return _sha256_bytes(_stable_json(canonical_analysis_config(config)).encode("utf-8"))


def analysis_cache_key(
    dataset: ValidatedDataset,
    config: object,
    engine_version: str = ANALYSIS_ENGINE_VERSION,
) -> str:
    payload = {
        "engine_version": engine_version,
        "dataset": canonical_dataset_payload(dataset),
        "config": canonical_analysis_config(config),
    }
    return _sha256_bytes(_stable_json(payload).encode("utf-8"))
