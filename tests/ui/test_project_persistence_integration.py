from types import SimpleNamespace


def test_validation_persists_new_dataset_when_research_project_is_open(monkeypatch) -> None:
    from metaphor_agreement_studio.ui.pages import validation

    old_context = SimpleNamespace(project=SimpleNamespace(name="Study"), dataset=None)
    new_dataset = object()
    new_context = SimpleNamespace(
        project=SimpleNamespace(name="Study"),
        dataset=new_dataset,
        current_dataset_version=SimpleNamespace(display_id="v2.0"),
        current_analysis_version=None,
    )
    calls = []

    def fake_save(context, dataset, reason, source_paths=()):
        calls.append((context, dataset, reason, tuple(source_paths)))
        return new_context

    monkeypatch.setattr(validation, "save_dataset_version", fake_save)
    state = {
        "workspace_mode": "research_project",
        "project_context": old_context,
        "dataset_status": "validated",
        "validated_dataset": new_dataset,
        "selected_workbook_path": None,
        "additional_workbooks": [],
    }

    result = validation.persist_validated_dataset_if_project(state, new_dataset)

    assert result is new_context
    assert calls[0][0] is old_context
    assert calls[0][1] is new_dataset
    assert "validated" in calls[0][2].casefold()
    assert state["project_context"] is new_context
    assert state["dataset_version"] == "v2.0"


def test_statistics_records_analysis_config_only_in_research_project(monkeypatch) -> None:
    from metaphor_agreement_studio.ui.pages import statistics

    old_context = SimpleNamespace(project=SimpleNamespace(name="Study"), dataset=object())
    updated_context = SimpleNamespace(
        project=SimpleNamespace(name="Study"),
        dataset=old_context.dataset,
        current_dataset_version=SimpleNamespace(display_id="v1.0"),
        current_analysis_version=SimpleNamespace(display_id="A-001"),
    )
    calls = []

    def fake_record(context, config):
        calls.append((context, config))
        return updated_context

    monkeypatch.setattr(statistics, "record_analysis_version", fake_record)
    state = {
        "workspace_mode": "research_project",
        "project_context": old_context,
        "dataset_status": "validated",
        "validated_dataset": old_context.dataset,
    }
    config = {"confidence_level": 0.95}

    result = statistics.persist_analysis_if_project(state, config)

    assert result is updated_context
    assert calls == [(old_context, config)]
    assert state["analysis_version"] == "A-001"


def test_quick_analysis_does_not_write_project_versions(monkeypatch) -> None:
    from metaphor_agreement_studio.ui.pages import statistics

    monkeypatch.setattr(
        statistics,
        "record_analysis_version",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not persist")),
    )
    state = {"workspace_mode": "quick_analysis", "project_context": None}
    assert statistics.persist_analysis_if_project(state, {"confidence": 0.95}) is None
