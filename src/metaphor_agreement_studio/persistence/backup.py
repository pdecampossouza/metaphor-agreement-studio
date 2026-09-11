from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import zipfile

from metaphor_agreement_studio.persistence.project_service import open_project
from metaphor_agreement_studio.persistence.types import ProjectContext


class InvalidProjectArchive(ValueError):
    """Raised when a portable project archive is unsafe or incomplete."""


_EXCLUDED_DIR_NAMES = {".git", ".venv", ".pytest_cache", "__pycache__", "backups"}
_EXCLUDED_SUFFIXES = ("-wal", "-shm")


def _checkpoint_database(project_root: Path) -> None:
    db_path = project_root / "project.db"
    if not db_path.is_file():
        raise ValueError("project.db is missing from the selected project.")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _archive_members(project_root: Path):
    for path in sorted(project_root.rglob("*")):
        relative = path.relative_to(project_root)
        if any(part in _EXCLUDED_DIR_NAMES for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.name.endswith(_EXCLUDED_SUFFIXES):
            continue
        yield path, relative


def create_backup(project_root: Path, destination: Path | None = None) -> Path:
    project_root = Path(project_root).expanduser().resolve(strict=True)
    open_project(project_root)
    _checkpoint_database(project_root)
    if destination is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = project_root / "backups" / f"{project_root.name}-{stamp}.masproject.zip"
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffixes[-2:] != [".masproject", ".zip"]:
        if destination.suffix.lower() == ".zip":
            destination = destination.with_name(destination.stem + ".masproject.zip")
        else:
            destination = destination.with_name(destination.name + ".masproject.zip")

    temp = destination.with_name(f".{destination.name}.tmp")
    temp.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path, relative in _archive_members(project_root):
                if path.resolve() == destination.resolve() or path.resolve() == temp.resolve():
                    continue
                zf.write(path, relative.as_posix())
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def _safe_member(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if member.is_absolute() or ".." in member.parts or not member.parts:
        raise InvalidProjectArchive("The project archive contains an unsafe file path.")
    if member.parts[0].endswith(":"):
        raise InvalidProjectArchive("The project archive contains an unsafe file path.")
    return member


def _reject_symlink(info: zipfile.ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise InvalidProjectArchive("Project archives may not contain symbolic links.")


def restore_backup(archive: Path, destination_root: Path) -> ProjectContext:
    archive = Path(archive).expanduser().resolve(strict=True)
    destination_root = Path(destination_root).expanduser().resolve()
    if destination_root.exists():
        raise FileExistsError(f"Restore destination already exists: {destination_root}")
    destination_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{destination_root.name}.restore-", dir=destination_root.parent)
    )
    try:
        try:
            with zipfile.ZipFile(archive) as zf:
                infos = zf.infolist()
                if not infos:
                    raise InvalidProjectArchive("The project archive is empty.")
                for info in infos:
                    member = _safe_member(info.filename)
                    _reject_symlink(info)
                    target = temp_root.joinpath(*member.parts)
                    resolved_target = target.resolve()
                    if temp_root.resolve() not in resolved_target.parents and resolved_target != temp_root.resolve():
                        raise InvalidProjectArchive("The project archive contains an unsafe file path.")
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            raise InvalidProjectArchive("The selected file is not a valid project archive.") from exc

        try:
            open_project(temp_root)
        except Exception as exc:
            raise InvalidProjectArchive(
                "The archive does not contain a valid Metaphor Agreement Studio project."
            ) from exc
        temp_root.replace(destination_root)
        return open_project(destination_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
