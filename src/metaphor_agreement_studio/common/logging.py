from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Any

_ALLOWED_CONTEXT_KEYS = {
    "event_type",
    "request_id",
    "source_filename",
    "sheet",
    "cell",
    "project_id",
    "dataset_id",
    "analysis_id",
}


def sanitize_log_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    if not context:
        return {}
    sanitized: dict[str, str] = {}
    for key in _ALLOWED_CONTEXT_KEYS:
        value = context.get(key)
        if value is None:
            continue
        sanitized[key] = str(value)[:500]
    return sanitized


def log_exception(
    exc: Exception,
    *,
    request_id: str,
    log_dir: Path,
    context: Mapping[str, Any] | None = None,
) -> Path:
    root = Path(log_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "metaphor_agreement_studio.log"
    payload = {
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "exception_type": type(exc).__name__,
        **sanitize_log_context(context),
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return target
