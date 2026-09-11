from __future__ import annotations

import os
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.persistence.backup import create_backup, restore_backup
from metaphor_agreement_studio.persistence.project_service import (
    create_project,
    record_analysis_version,
)
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.validation.service import ValidationService


def _decisions(draft) -> tuple[ValidationDecision, ...]:
    decisions: list[ValidationDecision] = []
    for index, issue in enumerate(draft.issues, start=1):
        if not issue.blocks_validation:
            continue
        if issue.code == "category_normalization_decision":
            decision_type = "category_normalization"
            validated_value = "Adjective"
        elif issue.code in {"confirm_annotation_mapping", "annotation_mapping_conflict"}:
            decision_type = "annotation_mapping"
            validated_value = "confirm_green_metaphor_red_non_metaphor"
        elif issue.code == "aggregate_role_decision":
            decision_type = "aggregate_role"
            validated_value = "aggregate"
        else:
            raise AssertionError(issue.code)
        decisions.append(
            ValidationDecision(
                decision_id=f"phase5-{index}",
                decision_type=decision_type,
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=validated_value,
                reason="Phase 5 persistence regression",
                decided_at="2026-09-05T22:00:00+01:00",
            )
        )
    return tuple(decisions)


def test_real_workbook_project_backup_round_trip_when_available(tmp_path: Path) -> None:
    raw = os.environ.get("MAS_EDUARDO_WORKBOOK")
    if not raw:
        pytest.skip("Set MAS_EDUARDO_WORKBOOK to run the research-project regression.")
    workbook = Path(raw)
    service = ValidationService()
    draft = service.prepare(inspect_workbook(workbook))
    dataset = service.validate(draft, _decisions(draft))

    context = create_project(tmp_path / "study", "Eduardo-Braulio Study", dataset, [workbook])
    config = AnalysisConfig(bootstrap_samples=0)
    context = record_analysis_version(context, config)
    bundle = analyze_dataset(context.dataset, config)
    archive = create_backup(context.root, tmp_path / "study.masproject.zip")
    restored = restore_backup(archive, tmp_path / "restored")
    restored_bundle = analyze_dataset(restored.dataset, config)

    assert bundle.counts.lexical_units == 97
    assert restored_bundle.counts.lexical_units == 97
    assert restored_bundle.pairwise[0].kappa.value == pytest.approx(0.4781829049611476)
    assert restored_bundle.cochran_q.q == pytest.approx(27.0)
    assert restored.current_dataset_version.content_hash == context.current_dataset_version.content_hash
    assert restored.current_analysis_version.config_hash == context.current_analysis_version.config_hash
    assert len(restored.source_files) == 1
    assert restored.source_files[0].stored_path.read_bytes() == workbook.read_bytes()
