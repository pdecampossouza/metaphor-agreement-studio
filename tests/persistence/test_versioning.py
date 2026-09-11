from dataclasses import replace
from pathlib import Path

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset, ValidationDecision
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.persistence.db import initialize_database, open_database
from metaphor_agreement_studio.persistence.types import ArtifactRecord
from metaphor_agreement_studio.persistence.versioning import (
    AnalysisVersionService,
    DatasetVersionService,
    artifact_is_current,
)


def _dataset() -> ValidatedDataset:
    source = Source("s1", "Song A")
    unit = LexicalUnit("u1", "fire", "Noun", "s1", 1)
    raters = (Rater("r1", "Braulio"), Rater("r2", "Eduardo"))
    annotations = (
        Annotation(
            "a1", "u1", "r1", Classification.METAPHOR, "imp", "Sheet1", "D1",
            "SIM", {}, "fixture", ValidationStatus.VALIDATED,
        ),
        Annotation(
            "a2", "u1", "r2", Classification.NON_METAPHOR, "imp", "Sheet1", "E1",
            "NAO", {}, "fixture", ValidationStatus.VALIDATED,
        ),
    )
    return ValidatedDataset("d1", (source,), (unit,), raters, annotations, (), ())


def _services(tmp_path: Path):
    db_path = tmp_path / "project.db"
    initialize_database(db_path)
    conn = open_database(db_path)
    return conn, DatasetVersionService(conn), AnalysisVersionService(conn)


def test_identical_canonical_dataset_reuses_version(tmp_path: Path) -> None:
    conn, datasets, _ = _services(tmp_path)
    try:
        first = datasets.create_if_changed(_dataset(), "initial")
        again = datasets.create_if_changed(replace(_dataset(), dataset_id="transient-other-id"), "save")
        assert first.version_id == again.version_id
        assert first.ordinal == 1
    finally:
        conn.close()


def test_relevant_dataset_changes_create_new_version(tmp_path: Path) -> None:
    conn, datasets, _ = _services(tmp_path)
    base = _dataset()
    try:
        v1 = datasets.create_if_changed(base, "initial")
        changed_annotation = replace(
            base,
            annotations=(replace(base.annotations[0], classification=Classification.NON_METAPHOR),) + base.annotations[1:],
        )
        v2 = datasets.create_if_changed(changed_annotation, "annotation corrected")
        changed_raters = replace(base, raters=base.raters + (Rater("r3", "Sofia"),))
        v3 = datasets.create_if_changed(changed_raters, "rater added")
        changed_unit = replace(base, units=(replace(base.units[0], grammatical_category="Verb"),))
        v4 = datasets.create_if_changed(changed_unit, "category normalized")
        changed_decision = replace(
            base,
            validation_decisions=(ValidationDecision("vd1", "alignment", "u1", None, "u1", "confirmed", "now"),),
        )
        v5 = datasets.create_if_changed(changed_decision, "alignment resolved")
        changed_source = replace(base, sources=(replace(base.sources[0], display_name="Song A / revised"),))
        v6 = datasets.create_if_changed(changed_source, "source hierarchy changed")

        assert [v.ordinal for v in (v1, v2, v3, v4, v5, v6)] == [1, 2, 3, 4, 5, 6]
        assert len({v.content_hash for v in (v1, v2, v3, v4, v5, v6)}) == 6
    finally:
        conn.close()


def test_analysis_versions_are_independent_from_dataset_versions(tmp_path: Path) -> None:
    conn, datasets, analyses = _services(tmp_path)
    try:
        dataset_version = datasets.create_if_changed(_dataset(), "initial")
        a1 = analyses.record(dataset_version, {"confidence_level": 0.95, "correction": "holm"})
        same = analyses.record(dataset_version, {"correction": "holm", "confidence_level": 0.95})
        a2 = analyses.record(dataset_version, {"confidence_level": 0.99, "correction": "holm"})
        a3 = analyses.record(dataset_version, {"confidence_level": 0.95, "correction": "benjamini-hochberg"})

        assert a1.analysis_id == same.analysis_id
        assert [a.ordinal for a in (a1, a2, a3)] == [1, 2, 3]
        assert all(a.dataset_version_id == dataset_version.version_id for a in (a1, a2, a3))
    finally:
        conn.close()


def test_artifact_freshness_requires_matching_dataset_and_analysis() -> None:
    artifact = ArtifactRecord("f1", "figure", "exports/a.svg", "abc", "now", "v1", "a1", {})
    assert artifact_is_current(artifact, "v1", "a1") is True
    assert artifact_is_current(artifact, "v2", "a1") is False
    assert artifact_is_current(artifact, "v1", "a2") is False
