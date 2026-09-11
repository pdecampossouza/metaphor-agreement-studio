from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from metaphor_agreement_studio.persistence.types import StoredSourceFile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stored_record(path: Path, project_root: Path, original_name: str, digest: str) -> StoredSourceFile:
    return StoredSourceFile(
        file_id=f"file_{digest[:24]}",
        original_name=original_name,
        stored_path=path,
        stored_relpath=path.relative_to(project_root).as_posix(),
        sha256=digest,
        byte_length=path.stat().st_size,
        imported_at=_now_iso(),
    )


def store_source_file(source: Path, project_root: Path) -> StoredSourceFile:
    source = Path(source).expanduser().resolve(strict=True)
    project_root = Path(project_root).expanduser().resolve()
    target_dir = project_root / "source_files"
    target_dir.mkdir(parents=True, exist_ok=True)
    source_hash = sha256_file(source)

    for existing in target_dir.iterdir():
        if existing.is_file() and sha256_file(existing) == source_hash:
            return _stored_record(existing, project_root, source.name, source_hash)

    target = target_dir / source.name
    if target.exists():
        target = target_dir / f"{source.stem}-{source_hash[:8]}{source.suffix}"

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target_dir)
    os.close(fd)
    Path(temp_name).unlink(missing_ok=True)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        copied_hash = sha256_file(temp_path)
        if copied_hash != source_hash:
            raise IOError("Source workbook copy failed hash verification.")
        temp_path.replace(target)
    finally:
        temp_path.unlink(missing_ok=True)

    return _stored_record(target, project_root, source.name, source_hash)
