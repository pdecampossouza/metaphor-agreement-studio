from pathlib import Path
import json

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset, ValidationDecision
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.persistence.db import open_database
from metaphor_agreement_studio.persistence.project_service import create_project, open_project
from metaphor_agreement_studio.state.session import (
    PROJECT_CONTEXT_KEY,
    WORKSPACE_MODE_KEY,
    ensure_session_state,
)


def _dataset() -> ValidatedDataset:
    decision = ValidationDecision(
        "vd1", "category_normalization", "Adjetive", "Adjetive", "Adjective",
        "Spelling normalization", "2026-09-05T20:00:00+00:00", "Researcher",
    )
    source = Source("s1", "Song A")
    unit = LexicalUnit("u1", "fire", "Adjective", "s1", 1)
    raters = (Rater("r1", "Braulio"), Rater("r2", "Eduardo"))
    annotations = (
        Annotation("a1", "u1", "r1", Classification.METAPHOR, "imp1", "Sheet1", "D1", "SIM", {"fg_rgb": "00FF00"}, "cell fill", ValidationStatus.VALIDATED),
        Annotation("a2", "u1", "r2", Classification.NON_METAPHOR, "imp1", "Sheet1", "E1", "NAO", {"fg_rgb": "FF0000"}, "cell fill", ValidationStatus.VALIDATED),
    )
    return ValidatedDataset("d1", (source,), (unit,), raters, annotations, (), (decision,))


def test_create_project_builds_self_contained_folder(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "ratings.xlsx"
    source.parent.mkdir()
    source.write_bytes(b"workbook")
    root = tmp_path / "My Study"

    context = create_project(root, "My Study", _dataset(), [source])

    expected_dirs = [
        "source_files", "exports/tables", "exports/figures", "exports/latex",
        "exports/datasets", "reports", "backups",
    ]
    assert all((root / name).is_dir() for name in expected_dirs)
    assert (root / "project.db").is_file()
    identity = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert identity["project_id"] == context.project.project_id
    assert identity["name"] == "My Study"
    assert identity["app_version"]
    assert len(list((root / "source_files").iterdir())) == 1
    assert source.read_bytes() == b"workbook"


def test_quick_analysis_conversion_round_trips_validated_dataset(tmp_path: Path) -> None:
    source = tmp_path / "ratings.xlsx"
    source.write_bytes(b"source bytes")
    dataset = _dataset()
    root = tmp_path / "project"

    created = create_project(root, "Metaphor Study", dataset, [source])
    reopened = open_project(root)

    assert reopened.project.project_id == created.project.project_id
    assert reopened.dataset.sources == dataset.sources
    assert reopened.dataset.units == dataset.units
    assert reopened.dataset.raters == dataset.raters
    assert reopened.dataset.annotations == dataset.annotations
    assert reopened.dataset.validation_decisions == dataset.validation_decisions
    assert reopened.current_dataset_version.content_hash == created.current_dataset_version.content_hash


def test_project_creation_records_research_audit_events(tmp_path: Path) -> None:
    source = tmp_path / "ratings.xlsx"
    source.write_bytes(b"source bytes")
    root = tmp_path / "project"

    create_project(root, "Metaphor Study", _dataset(), [source])

    with open_database(root / "project.db") as conn:
        event_types = [row[0] for row in conn.execute("SELECT event_type FROM audit_events ORDER BY rowid")]
    assert event_types == [
        "project_created",
        "source_file_added",
        "dataset_saved",
        "quick_analysis_saved_as_project",
    ]


def test_session_defaults_to_unsaved_quick_analysis() -> None:
    state = {}
    ensure_session_state(state)
    assert state[WORKSPACE_MODE_KEY] == "quick_analysis"
    assert state[PROJECT_CONTEXT_KEY] is None


def test_research_project_dataset_change_creates_new_version_and_stales_old_analysis(tmp_path: Path) -> None:
    from dataclasses import replace

    from metaphor_agreement_studio.persistence.project_service import (
        record_analysis_version,
        save_dataset_version,
    )

    source = tmp_path / "ratings.xlsx"
    source.write_bytes(b"source")
    context = create_project(tmp_path / "project-versioned", "Study", _dataset(), [source])
    analyzed = record_analysis_version(context, {"confidence_level": 0.95, "correction": "holm"})
    changed = replace(
        analyzed.dataset,
        annotations=(
            replace(analyzed.dataset.annotations[0], classification=Classification.NON_METAPHOR),
            analyzed.dataset.annotations[1],
        ),
    )

    updated = save_dataset_version(analyzed, changed, "Expert classification corrected")

    assert updated.current_dataset_version.ordinal == 2
    assert updated.current_analysis_version.ordinal == 1
    assert updated.current_analysis_version.dataset_version_id != updated.current_dataset_version.version_id
    assert updated.dataset.annotations[0].classification is Classification.NON_METAPHOR


def test_record_analysis_version_changes_only_analysis_version(tmp_path: Path) -> None:
    from metaphor_agreement_studio.persistence.project_service import record_analysis_version

    source = tmp_path / "ratings.xlsx"
    source.write_bytes(b"source")
    context = create_project(tmp_path / "project-analysis", "Study", _dataset(), [source])
    before_dataset_hash = context.current_dataset_version.content_hash

    a1 = record_analysis_version(context, {"confidence_level": 0.95, "correction": "holm"})
    a2 = record_analysis_version(a1, {"confidence_level": 0.99, "correction": "holm"})

    assert a1.current_analysis_version.ordinal == 1
    assert a2.current_analysis_version.ordinal == 2
    assert a2.current_dataset_version.content_hash == before_dataset_hash


def test_save_dataset_version_preserves_new_source_workbook(tmp_path: Path) -> None:
    from metaphor_agreement_studio.persistence.project_service import save_dataset_version

    first = tmp_path / "ratings.xlsx"
    first.write_bytes(b"first")
    context = create_project(tmp_path / "project-add-source", "Study", _dataset(), [first])
    second = tmp_path / "sofia.xlsx"
    second.write_bytes(b"second")

    updated = save_dataset_version(context, context.dataset, "Additional source preserved", source_paths=[second])

    assert len(updated.source_files) == 2
    assert {item.original_name for item in updated.source_files} == {"ratings.xlsx", "sofia.xlsx"}
    assert any(event.event_type == "source_file_added" and "sofia.xlsx" in event.summary for event in updated.audit_events)
