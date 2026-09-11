from pathlib import Path

from metaphor_agreement_studio.persistence.types import (
    AnalysisVersionRecord,
    DatasetVersionRecord,
    ProjectContext,
    ProjectRecord,
)
from metaphor_agreement_studio.ui.pages.project import project_page_state
from metaphor_agreement_studio.ui.shell import status_strip_parts


def _context(tmp_path: Path, *, stale: bool = False) -> ProjectContext:
    project = ProjectRecord("p1", "Metaphor Study", "now", "now", "0.5.0")
    dataset = DatasetVersionRecord("d2" if stale else "d1", 2 if stale else 1, "now", "change", "hash", "{}")
    analysis = AnalysisVersionRecord("a1", 1, "d1", "now", "{}", "config")
    return ProjectContext(tmp_path, project, dataset, analysis)


def test_quick_analysis_status_is_explicitly_unsaved() -> None:
    state = {
        "workspace_mode": "quick_analysis",
        "dataset_status": "validated",
        "project_name": "Quick Analysis",
        "dataset_version": None,
        "analysis_version": None,
        "validated_dataset": None,
        "project_context": None,
    }
    assert status_strip_parts(state)[:3] == ["Dataset validated", "Quick Analysis", "Not saved"]


def test_project_page_allows_save_only_for_validated_temporary_session() -> None:
    validated = {
        "workspace_mode": "quick_analysis",
        "dataset_status": "validated",
        "validated_dataset": object(),
        "project_context": None,
    }
    pending = dict(validated, dataset_status="not_validated")
    research = dict(validated, workspace_mode="research_project", project_context=object())

    assert project_page_state(validated)["can_save_as_project"] is True
    assert project_page_state(pending)["can_save_as_project"] is False
    assert project_page_state(research)["can_save_as_project"] is False


def test_status_strip_marks_analysis_out_of_date_when_dataset_advanced(tmp_path: Path) -> None:
    state = {
        "workspace_mode": "research_project",
        "dataset_status": "validated",
        "project_name": "Metaphor Study",
        "dataset_version": "v2.0",
        "analysis_version": "A-001",
        "validated_dataset": None,
        "project_context": _context(tmp_path, stale=True),
    }
    parts = status_strip_parts(state)
    assert "Dataset modified" in parts
    assert "Analysis out of date" in parts
    assert "Re-run analysis" in parts


def test_current_project_status_shows_project_version_ids(tmp_path: Path) -> None:
    state = {
        "workspace_mode": "research_project",
        "dataset_status": "validated",
        "project_name": "Metaphor Study",
        "validated_dataset": None,
        "project_context": _context(tmp_path, stale=False),
    }
    parts = status_strip_parts(state)
    assert "v1.0" in parts
    assert "Analysis A-001" in parts
    assert "Metaphor Study" in parts


def test_project_page_exposes_backup_only_for_open_research_project(tmp_path: Path) -> None:
    research_state = {
        "workspace_mode": "research_project",
        "dataset_status": "validated",
        "validated_dataset": object(),
        "project_context": _context(tmp_path, stale=False),
    }
    quick_state = {
        "workspace_mode": "quick_analysis",
        "dataset_status": "validated",
        "validated_dataset": object(),
        "project_context": None,
    }
    assert project_page_state(research_state)["can_backup"] is True
    assert project_page_state(quick_state)["can_backup"] is False


def test_project_discovery_finds_saved_projects_and_portable_backups(tmp_path: Path) -> None:
    from metaphor_agreement_studio.ui.pages.project import discover_backup_archives, discover_project_roots

    project = tmp_path / "projects" / "study-a"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    (project / "project.db").write_bytes(b"db")
    backup = project / "backups" / "study-a.masproject.zip"
    backup.parent.mkdir()
    backup.write_bytes(b"zip")
    unrelated = tmp_path / "projects" / "not-a-project"
    unrelated.mkdir()

    assert discover_project_roots(tmp_path) == (project.resolve(),)
    assert discover_backup_archives(tmp_path) == (backup.resolve(),)
