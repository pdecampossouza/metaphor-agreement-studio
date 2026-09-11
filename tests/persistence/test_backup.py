from pathlib import Path
import zipfile

import pytest

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.persistence.backup import InvalidProjectArchive, create_backup, restore_backup
from metaphor_agreement_studio.persistence.db import open_database
from metaphor_agreement_studio.persistence.project_service import create_project, open_project
from metaphor_agreement_studio.persistence.versioning import AnalysisVersionService


def _dataset() -> ValidatedDataset:
    return ValidatedDataset(
        "d1",
        (Source("s1", "Song"),),
        (LexicalUnit("u1", "fire", "Noun", "s1", 1),),
        (Rater("r1", "Braulio"), Rater("r2", "Eduardo")),
        (
            Annotation("a1", "u1", "r1", Classification.METAPHOR, "imp", "Sheet1", "D1", "SIM", {}, "fixture", ValidationStatus.VALIDATED),
            Annotation("a2", "u1", "r2", Classification.NON_METAPHOR, "imp", "Sheet1", "E1", "NAO", {}, "fixture", ValidationStatus.VALIDATED),
        ),
        (),
        (),
    )


def _project(tmp_path: Path) -> Path:
    source = tmp_path / "ratings.xlsx"
    source.write_bytes(b"workbook")
    root = tmp_path / "study"
    context = create_project(root, "Study", _dataset(), [source])
    with open_database(root / "project.db") as conn:
        AnalysisVersionService(conn).record(context.current_dataset_version, {"confidence": 0.95})
    (root / "exports" / "figures" / "figure_metadata.json").write_text('{"figure": 1}', encoding="utf-8")
    (root / "reports" / "import_report.txt").write_text("validated", encoding="utf-8")
    return root


def test_backup_contains_project_source_and_research_outputs(tmp_path: Path) -> None:
    root = _project(tmp_path)
    archive = create_backup(root)

    assert archive.suffixes[-2:] == [".masproject", ".zip"]
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert "project.db" in names
    assert "project.json" in names
    assert any(name.startswith("source_files/") for name in names)
    assert "exports/figures/figure_metadata.json" in names
    assert "reports/import_report.txt" in names
    assert not any(name.endswith("-wal") or name.endswith("-shm") for name in names)


def test_restore_rejects_zip_slip_without_writing_outside(tmp_path: Path) -> None:
    archive = tmp_path / "evil.masproject.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../outside.txt", "bad")

    with pytest.raises(InvalidProjectArchive):
        restore_backup(archive, tmp_path / "restored")
    assert not (tmp_path.parent / "outside.txt").exists()


def test_backup_restore_round_trip_preserves_versions_sources_and_audit(tmp_path: Path) -> None:
    root = _project(tmp_path)
    before = open_project(root)
    archive = create_backup(root, tmp_path / "portable.masproject.zip")

    restored = restore_backup(archive, tmp_path / "restored-study")

    assert restored.current_dataset_version.content_hash == before.current_dataset_version.content_hash
    assert restored.current_analysis_version.config_hash == open_project(root).current_analysis_version.config_hash
    assert [f.sha256 for f in restored.source_files] == [f.sha256 for f in before.source_files]
    assert len(restored.audit_events) == len(before.audit_events)
    assert (restored.root / "exports" / "figures" / "figure_metadata.json").is_file()
