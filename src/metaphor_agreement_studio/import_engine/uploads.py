from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from metaphor_agreement_studio.config import SUPPORTED_WORKBOOK_SUFFIXES
from metaphor_agreement_studio.common.errors import UnsupportedWorkbookError
from metaphor_agreement_studio.domain.imports import UploadedWorkbook


def _validate_display_name(display_name: str) -> tuple[str, str]:
    if not display_name or "/" in display_name or "\\" in display_name:
        raise UnsupportedWorkbookError("Please select a workbook file directly, not a folder path.")
    if display_name.startswith("~$"):
        raise UnsupportedWorkbookError("Temporary Excel files beginning with '~$' cannot be imported.")
    suffix = Path(display_name).suffix.casefold()
    if suffix not in SUPPORTED_WORKBOOK_SUFFIXES:
        raise UnsupportedWorkbookError("Only .xlsx and .xlsm workbook files are supported.")
    return Path(display_name).stem, suffix


def _safe_stem(stem: str) -> str:
    normalized = unicodedata.normalize("NFKC", stem).strip()
    sanitized = re.sub(r"[^\w.-]+", "_", normalized, flags=re.UNICODE).strip("._")
    return sanitized or "workbook"


def materialize_upload(display_name: str, data: bytes, session_root: Path) -> UploadedWorkbook:
    stem, suffix = _validate_display_name(display_name)
    root = Path(session_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    filename = f"{_safe_stem(stem)}--{digest[:12]}{suffix}"
    destination = (root / filename).resolve()
    if not destination.is_relative_to(root):
        raise UnsupportedWorkbookError("The uploaded workbook name could not be stored safely.")

    if not destination.exists():
        file_descriptor, temporary_name = tempfile.mkstemp(prefix=".mas-upload-", dir=root)
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    return UploadedWorkbook(
        local_path=destination,
        original_display_name=display_name,
        byte_length=len(data),
        sha256=digest,
    )
