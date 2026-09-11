from pathlib import Path

APP_NAME = "Metaphor Agreement Studio"
APP_SUBTITLE = "Inter-rater analysis for lexical metaphor annotation"
SUPPORTED_WORKBOOK_SUFFIXES = (".xlsx", ".xlsm")


def default_scan_roots(base_dir: Path) -> tuple[Path, ...]:
    return (base_dir, base_dir / "imports")
