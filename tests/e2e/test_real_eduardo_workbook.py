from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.validation.service import ValidationService


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workbook_path() -> Path:
    raw = os.environ.get("MAS_EDUARDO_WORKBOOK")
    if raw:
        return Path(raw).expanduser().resolve()
    for candidate in (
        Path.cwd() / "Teste de Concordância - Revisor Eduardo.xlsx",
        Path.cwd() / "Teste de Concordancia - Revisor Eduardo.xlsx",
        Path.cwd() / "imports" / "Teste de Concordância - Revisor Eduardo.xlsx",
        Path.cwd() / "imports" / "Teste de Concordancia - Revisor Eduardo.xlsx",
    ):
        if candidate.is_file():
            return candidate.resolve()
    pytest.skip("Eduardo workbook is not available in this environment.")


def _decisions(draft):
    output = []
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
            raise AssertionError(f"Unhandled blocking issue: {issue.code}")
        output.append(
            ValidationDecision(
                decision_id=f"eduardo-{index}",
                decision_type=issue.decision_type or "",
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=value,
                reason="Phase 7 real-workbook acceptance regression",
                decided_at="2026-09-06T00:20:00+01:00",
            )
        )
    return tuple(output)


def test_real_eduardo_workbook_acceptance_regression() -> None:
    path = _workbook_path()
    before = _sha256(path)

    service = ValidationService()
    inspection = inspect_workbook(path)
    draft = service.prepare(inspection)

    assert inspection.sheet_names == ("Planilha1",)
    assert [table.row_count for table in draft.tables] == [10, 22, 37, 28, 97]
    assert {r.display_name for r in draft.rater_mappings} == {"Eduardo", "Bráulio"}
    assert any(
        proposal.original == "Adjetive" and proposal.proposed == "Adjective"
        for proposal in draft.normalization_proposals
    )
    assert any(
        candidate.matched_units == 97 and candidate.coverage == 1.0
        for candidate in draft.aggregate_candidates
    )

    dataset = service.validate(draft, _decisions(draft))
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    assert bundle.counts.lexical_units == 97
    assert len(bundle.pairwise) == 1
    assert bundle.pairwise[0].kappa.status.value in {"ok", "descriptive_only"}
    assert bundle.cochran_q is not None
    assert bundle.cochran_q.status.value in {
        "ok",
        "not_estimable_no_variation",
        "incomplete_for_metric",
    }
    assert bundle.by_category
    for group in bundle.by_category:
        assert group.pairwise
        assert group.pairwise[0].kappa.status.value
        assert group.cochran_q is not None
        assert group.cochran_q.status.value

    after = _sha256(path)
    assert after == before
