from __future__ import annotations

from pathlib import Path

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.persistence.project_service import create_project, open_project, record_analysis_version
from metaphor_agreement_studio.persistence.versioning import canonical_dataset_payload
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.validation.service import ValidationService
from tests.fixtures.workbook_factory import build_two_rater_workbook


def _dataset(path: Path):
    service = ValidationService()
    draft = service.prepare(inspect_workbook(path))
    decisions = []
    for index, issue in enumerate(draft.issues, start=1):
        if not issue.blocks_validation:
            continue
        if issue.code == "category_normalization_decision":
            value = "Adjective"
        elif issue.code in {"confirm_annotation_mapping", "annotation_mapping_conflict"}:
            value = "confirm_green_metaphor_red_non_metaphor"
        elif issue.code == "aggregate_role_decision":
            value = "aggregate"
        else:
            raise AssertionError(issue.code)
        decisions.append(
            ValidationDecision(
                decision_id=f"d{index}",
                decision_type=issue.decision_type or "",
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=value,
                reason="Project round-trip",
                decided_at="2026-09-06T00:05:00+01:00",
            )
        )
    return service.validate(draft, tuple(decisions))


def test_project_round_trip_reproduces_dataset_hash_and_statistics(tmp_path: Path) -> None:
    workbook = build_two_rater_workbook(tmp_path / "ratings.xlsx")
    dataset = _dataset(workbook)
    config = AnalysisConfig(bootstrap_samples=0)
    before = analyze_dataset(dataset, config)

    context = create_project(tmp_path / "project", "Round Trip", dataset, (workbook,))
    context = record_analysis_version(context, config)
    saved_hash = context.current_dataset_version.content_hash

    reopened = open_project(context.root)
    after = analyze_dataset(reopened.dataset, config)

    assert reopened.current_dataset_version.content_hash == saved_hash
    assert canonical_dataset_payload(reopened.dataset) == canonical_dataset_payload(dataset)
    assert after.pairwise[0].kappa.value == before.pairwise[0].kappa.value
    assert after.counts == before.counts
