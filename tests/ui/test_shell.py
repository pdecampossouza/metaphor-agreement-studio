from types import SimpleNamespace

from metaphor_agreement_studio.ui.shell import status_strip_parts


def test_validated_status_strip_reports_analytical_units_and_raters() -> None:
    dataset = SimpleNamespace(
        sources=(
            SimpleNamespace(source_id="a", is_aggregate=False),
            SimpleNamespace(source_id="agg", is_aggregate=True),
        ),
        units=(
            SimpleNamespace(source_id="a"),
            SimpleNamespace(source_id="a"),
            SimpleNamespace(source_id="agg"),
            SimpleNamespace(source_id="agg"),
        ),
        raters=(SimpleNamespace(), SimpleNamespace()),
    )
    state = {
        "dataset_status": "validated",
        "project_name": "Quick Analysis",
        "dataset_version": None,
        "analysis_version": None,
        "validated_dataset": dataset,
    }

    parts = status_strip_parts(state)

    assert parts[0] == "Dataset validated"
    assert "2 analytical units" in parts
    assert "2 raters" in parts
