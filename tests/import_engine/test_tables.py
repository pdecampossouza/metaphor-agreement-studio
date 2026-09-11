import os
from pathlib import Path

import pytest

from metaphor_agreement_studio.import_engine.tables import detect_tables
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.validation.aggregate import detect_aggregate_sources
from tests.fixtures.workbook_factory import build_tables_with_aggregate


def test_detects_separated_tables_from_semantic_headers(tmp_path: Path) -> None:
    path = build_tables_with_aggregate(tmp_path / "tables.xlsx")
    inspection = inspect_workbook(path)

    tables = detect_tables(inspection)

    assert [table.source_title for table in tables] == [
        "1. Video: A",
        "2. Video: B",
        "3. Combined Videos",
    ]
    assert [table.row_count for table in tables] == [2, 1, 3]
    assert [tuple(rater.display_name for rater in table.rater_columns) for table in tables] == [
        ("Eduardo", "Braulio"),
        ("Eduardo", "Braulio"),
        ("Eduardo", "Braulio"),
    ]
    assert tables[0].lexical_unit_column != tables[1].lexical_unit_column


def test_real_eduardo_workbook_structure_when_available() -> None:
    raw = os.environ.get("MAS_EDUARDO_WORKBOOK")
    if not raw:
        pytest.skip("Set MAS_EDUARDO_WORKBOOK to run the private research workbook regression.")
    inspection = inspect_workbook(Path(raw))

    tables = detect_tables(inspection)

    assert inspection.sheet_names == ("Planilha1",)
    assert len(tables) == 5
    assert tuple(table.row_count for table in tables) == (10, 22, 37, 28, 97)
    assert all(len(table.rater_columns) == 2 for table in tables)
    assert all(
        tuple(rater.display_name for rater in table.rater_columns) == ("Eduardo", "Bráulio")
        for table in tables
    )
    aggregates = detect_aggregate_sources(tables)
    assert len(aggregates) == 1
    assert aggregates[0].matched_units == 97
    assert aggregates[0].coverage == 1.0
