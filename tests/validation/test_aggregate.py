from pathlib import Path

from metaphor_agreement_studio.import_engine.tables import detect_tables
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.validation.aggregate import detect_aggregate_sources
from tests.fixtures.workbook_factory import build_tables_with_aggregate


def test_combined_table_is_proposed_as_aggregate(tmp_path: Path) -> None:
    path = build_tables_with_aggregate(tmp_path / "tables.xlsx")
    tables = detect_tables(inspect_workbook(path))

    candidates = detect_aggregate_sources(tables)

    assert len(candidates) == 1
    aggregate = candidates[0]
    assert aggregate.aggregate_source_title == "3. Combined Videos"
    assert aggregate.matched_units == 3
    assert aggregate.coverage == 1.0
    assert len(aggregate.component_table_ids) == 2
