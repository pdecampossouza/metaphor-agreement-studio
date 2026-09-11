from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.persistence.project_service import (
    create_project,
    record_analysis_version,
    register_artifact,
    save_dataset_version,
)
from metaphor_agreement_studio.persistence.versioning import artifact_is_current
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def dataset(value: Classification = Classification.METAPHOR) -> ValidatedDataset:
    unit = LexicalUnit("u1", "spider", "Noun", "s1", 1)
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"))
    anns = (
        Annotation("a1", "u1", "r1", value, "imp", "Sheet1", "D1", value.value, {}, "fixture", ValidationStatus.VALIDATED),
        Annotation("a2", "u1", "r2", value, "imp", "Sheet1", "E1", value.value, {}, "fixture", ValidationStatus.VALIDATED),
    )
    return ValidatedDataset("d1", (Source("s1", "Example"),), (unit,), raters, anns, (), ())


def test_register_artifact_tracks_versions_and_freshness(tmp_path: Path) -> None:
    source = tmp_path / "Eduardo.xlsx"
    source.write_bytes(b"original")
    context = create_project(tmp_path / "project", "Study", dataset(), (source,))
    context = record_analysis_version(context, AnalysisConfig(selected_rater_ids=("r1", "r2")))
    figure = tmp_path / "figure.pdf"
    figure.write_bytes(b"publication figure")
    context = register_artifact(context, figure, "figure", {"title": "Agreement by POS"})
    assert len(context.artifacts) == 1
    artifact = context.artifacts[0]
    assert (context.root / artifact.stored_relpath).exists()
    assert len(artifact.sha256) == 64
    assert artifact.dataset_version_id == context.current_dataset_version.version_id
    assert artifact.analysis_id == context.current_analysis_version.analysis_id
    assert artifact_is_current(artifact, context.current_dataset_version, context.current_analysis_version)

    changed = dataset(Classification.NON_METAPHOR)
    context = save_dataset_version(context, changed, "Changed classification")
    assert not artifact_is_current(artifact, context.current_dataset_version, context.current_analysis_version)
