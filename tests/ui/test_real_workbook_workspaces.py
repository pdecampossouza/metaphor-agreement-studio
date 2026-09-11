from __future__ import annotations

import os
from pathlib import Path

import pytest

from metaphor_agreement_studio.domain.imports import ValidationDecision
from metaphor_agreement_studio.import_engine.workbook import inspect_workbook
from metaphor_agreement_studio.review.service import build_rater_profile, build_review_cases
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig
from metaphor_agreement_studio.ui.filters import default_analysis_selection, default_reference_rater_id
from metaphor_agreement_studio.ui.pages.agreement import (
    build_pairwise_kappa_figure,
    build_rater_tendency_figure,
    rater_tendency_records,
)
from metaphor_agreement_studio.ui.pages.categories import category_overview_records
from metaphor_agreement_studio.ui.pages.review import (
    default_review_source_ids,
    filter_review_cases,
    review_summary,
)
from metaphor_agreement_studio.ui.pages.sources import split_source_groups
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
                decision_id=f"phase4-{index}",
                decision_type=decision_type,
                target_id=issue.target_id or "",
                original_value=None,
                validated_value=validated_value,
                reason="Phase 4 real-workbook regression",
                decided_at="2026-09-05T21:45:00+01:00",
            )
        )
    return tuple(decisions)


def test_real_workbook_analysis_workspaces_when_available() -> None:
    raw = os.environ.get("MAS_EDUARDO_WORKBOOK")
    if not raw:
        pytest.skip("Set MAS_EDUARDO_WORKBOOK to run the research-workbook Phase 4 regression.")

    service = ValidationService()
    draft = service.prepare(inspect_workbook(Path(raw)))
    dataset = service.validate(draft, _decisions(draft))
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))

    primary_sources = default_review_source_ids(dataset)
    cases = filter_review_cases(build_review_cases(dataset), mode="All cases", source_ids=primary_sources)
    summary = review_summary(cases)
    assert summary["total"] == 97
    assert summary["requires_review"] == 27
    assert summary["unanimous"] == 70

    primary, aggregate = split_source_groups(bundle.by_source, dataset)
    assert len(primary) == 4
    assert len(aggregate) == 1
    assert sum(group.lexical_unit_count for group in primary) == 97
    assert aggregate[0].lexical_unit_count == 97

    pair = bundle.pairwise[0]
    category_rows = category_overview_records(
        bundle.by_category,
        dataset,
        (pair.rater_a_id, pair.rater_b_id),
    )
    assert len(category_rows) == 8
    assert next(row for row in category_rows if row["Category"] == "Phrasal verb")["Cohen's κ"] == "Descriptive result only"

    braulio = default_reference_rater_id(dataset)
    assert braulio is not None
    profile = build_rater_profile(dataset, braulio, bundle)
    assert profile.total_units == 97
    assert profile.differs_from_all_count == 27

    selection = default_analysis_selection(dataset)
    matrix_figure = build_pairwise_kappa_figure(bundle, dataset)
    tendency_figure = build_rater_tendency_figure(rater_tendency_records(dataset, selection))
    assert matrix_figure.data[0].type == "heatmap"
    assert tendency_figure.data[0].type == "bar"
    assert len(tendency_figure.data[0].x) == 2
