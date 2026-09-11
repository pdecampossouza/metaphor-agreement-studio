from pathlib import Path

from metaphor_agreement_studio.config import (
    APP_NAME,
    APP_SUBTITLE,
    SUPPORTED_WORKBOOK_SUFFIXES,
    default_scan_roots,
)


def test_product_identity_and_local_scan_roots(tmp_path: Path) -> None:
    assert APP_NAME == "Metaphor Agreement Studio"
    assert APP_SUBTITLE == "Inter-rater analysis for lexical metaphor annotation"
    assert SUPPORTED_WORKBOOK_SUFFIXES == (".xlsx", ".xlsm")
    assert default_scan_roots(tmp_path) == (tmp_path, tmp_path / "imports")
