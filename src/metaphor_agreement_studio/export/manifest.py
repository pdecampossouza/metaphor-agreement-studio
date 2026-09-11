from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
import platform
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ManifestContext:
    project_name: str
    dataset_version: str
    analysis_version: str
    source_files: tuple[object, ...]
    raters: tuple[str, ...]
    source_groups: tuple[str, ...]
    analysis_settings: Mapping[str, Any]
    software_version: str
    generated_at: str | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _normal(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _normal(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_normal(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _source_record(item: object) -> dict[str, object]:
    if isinstance(item, Path):
        return {"name": item.name, "sha256": _sha256(item), "byte_length": item.stat().st_size}
    path = getattr(item, "stored_path", None)
    name = getattr(item, "original_name", None) or (Path(path).name if path else str(item))
    sha = getattr(item, "sha256", None)
    size = getattr(item, "byte_length", None)
    if path and (sha is None or size is None):
        source_path = Path(path)
        sha = sha or _sha256(source_path)
        size = size if size is not None else source_path.stat().st_size
    return {"name": str(name), "sha256": str(sha or ""), "byte_length": int(size or 0)}


def build_manifest(context: ManifestContext) -> dict[str, object]:
    generated_at = context.generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "project_name": context.project_name,
        "dataset_version": context.dataset_version,
        "analysis_version": context.analysis_version,
        "source_files": [_source_record(item) for item in context.source_files],
        "raters": list(context.raters),
        "source_groups": list(context.source_groups),
        "analysis_settings": _normal(dict(context.analysis_settings)),
        "software_version": context.software_version,
        "python_version": platform.python_version(),
        "runtime_platform": platform.platform(),
        "generated_at": generated_at,
    }
