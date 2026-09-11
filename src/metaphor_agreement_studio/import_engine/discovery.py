from pathlib import Path

from metaphor_agreement_studio.config import SUPPORTED_WORKBOOK_SUFFIXES
from metaphor_agreement_studio.domain.models import WorkbookCandidate


def discover_workbooks(roots: tuple[Path, ...]) -> tuple[WorkbookCandidate, ...]:
    seen: set[Path] = set()
    candidates: list[WorkbookCandidate] = []

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue

        for path in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            resolved = path.resolve()
            if (
                not path.is_file()
                or path.name.startswith("~$")
                or path.suffix.casefold() not in SUPPORTED_WORKBOOK_SUFFIXES
                or resolved in seen
            ):
                continue

            seen.add(resolved)
            candidates.append(
                WorkbookCandidate(
                    path=resolved,
                    display_name=path.name,
                    discovery_root=root.resolve(),
                )
            )

    return tuple(candidates)
