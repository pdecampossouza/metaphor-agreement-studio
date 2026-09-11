from pathlib import Path

from metaphor_agreement_studio.import_engine.colors import color_family, resolve_fill_color
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from tests.fixtures.workbook_factory import build_two_rater_workbook


def test_direct_rgb_fill_resolves_to_rgb_triplet(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    inspection = inspect_workbook(path)
    cell = inspection.sheet("Planilha1").cell("L29")

    resolved = resolve_fill_color(cell, inspection.workbook_theme)

    assert resolved.rgb == (244, 204, 204)
    assert resolved.source == "rgb"
    assert color_family(resolved.rgb) == "red"


def test_green_shades_are_recognized_as_green_family(tmp_path: Path) -> None:
    path = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    inspection = inspect_workbook(path)
    sheet = inspection.sheet("Planilha1")

    green_b = resolve_fill_color(sheet.cell("L30"), inspection.workbook_theme)
    green_a = resolve_fill_color(sheet.cell("M30"), inspection.workbook_theme)

    assert color_family(green_b.rgb) == "green"
    assert color_family(green_a.rgb) == "green"
