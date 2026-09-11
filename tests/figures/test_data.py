from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from metaphor_agreement_studio.figures.data import (
    build_category_agreement_data,
    build_pairwise_kappa_matrix_data,
    build_source_comparison_data,
)
from metaphor_agreement_studio.figures.provenance import write_provenance_sidecar
from metaphor_agreement_studio.figures.types import (
    FigureKind,
    FigureProvenance,
    FigureSpec,
    SEMANTIC_MARKERS,
)
from metaphor_agreement_studio.statistics.types import (
    AnalysisBundle,
    AnalysisConfig,
    CochranQResult,
    CountSummary,
    EstimateStatus,
    GroupResult,
    MetricResult,
    PairwiseResult,
)


def metric(name: str, value: float | None, n: int, low=None, high=None) -> MetricResult:
    return MetricResult(name, value, EstimateStatus.OK, n, ci_low=low, ci_high=high)


def pair(a: str, b: str, kappa: float, raw: float, n: int, low=None, high=None) -> PairwiseResult:
    return PairwiseResult(
        a,
        b,
        metric("raw_agreement", raw, n),
        metric("cohen_kappa", kappa, n, low, high),
        ((1, 0), (0, 1)),
    )


def bundle() -> AnalysisBundle:
    p = pair("r1", "r2", 0.5, 0.75, 4, 0.1, 0.8)
    noun = GroupResult("Noun", "Noun", 2, (pair("r1", "r2", 0.4, 0.5, 2, 0.0, 0.7),), None)
    verb = GroupResult("Verb", "Verb", 2, (pair("r1", "r2", 0.6, 1.0, 2, 0.2, 0.9),), None)
    source = GroupResult("s1", "Example", 4, (p,), None)
    return AnalysisBundle(
        config=AnalysisConfig(selected_rater_ids=("r1", "r2")),
        counts=CountSummary(4, 2, 8, 3, 5, 0, (("Noun", 2), ("Verb", 2))),
        pairwise=(p,),
        overall_multirater=(),
        cochran_q=CochranQResult(1.0, 1, 0.3, 4, EstimateStatus.OK),
        posthoc_tendency=(),
        specific_agreement=(),
        expert_benchmark=(),
        by_category=(noun, verb),
        by_source=(source,),
        warnings=(),
    )


def test_category_figure_data_preserves_n_estimate_and_ci() -> None:
    data = build_category_agreement_data(bundle(), rater_pair=("r1", "r2"))
    noun = data.frame.set_index("category").loc["Noun"]
    assert noun["n"] == 2
    assert noun["estimate"] == 0.4
    assert noun["ci_low"] == 0.0
    assert noun["ci_high"] == 0.7
    assert pd.api.types.is_numeric_dtype(data.frame["estimate"])


def test_pairwise_matrix_uses_numeric_kappa_and_neutral_diagonal() -> None:
    data = build_pairwise_kappa_matrix_data(bundle())
    assert set(data.frame.columns) >= {"rater_a", "rater_b", "estimate", "raw_agreement", "n"}
    diagonal = data.frame[data.frame["rater_a"] == data.frame["rater_b"]]
    assert diagonal["estimate"].isna().all()
    off_diag = data.frame[(data.frame["rater_a"] == "r1") & (data.frame["rater_b"] == "r2")]
    assert off_diag.iloc[0]["estimate"] == 0.5


def test_source_comparison_keeps_analytical_values_unformatted() -> None:
    data = build_source_comparison_data(bundle(), rater_pair=("r1", "r2"))
    assert data.frame.loc[0, "source"] == "Example"
    assert data.frame.loc[0, "estimate"] == 0.5
    assert "κ" not in str(data.frame.loc[0, "estimate"])


def test_figure_provenance_sidecar_serializes_exact_identifiers(tmp_path: Path) -> None:
    provenance = FigureProvenance(
        project_name="Metaphor Study",
        dataset_version="v1.0",
        analysis_version="A-003",
        raters=("Eduardo", "Braulio"),
        filters={"source": ["Kadouch"], "category": ["Noun"], "rater_pair": ["r1", "r2"]},
        software_version="0.6.0",
        generated_at="2026-09-05T22:00:00+00:00",
    )
    figure = tmp_path / "figure.pdf"
    figure.write_bytes(b"pdf")
    sidecar = write_provenance_sidecar(figure, provenance)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["dataset_version"] == "v1.0"
    assert payload["analysis_version"] == "A-003"
    assert payload["filters"]["rater_pair"] == ["r1", "r2"]
    assert "source_workbook_raw" not in payload


def test_accessible_visual_semantics_do_not_depend_on_color() -> None:
    assert SEMANTIC_MARKERS["Metaphor"] != SEMANTIC_MARKERS["Non-metaphor"]
    assert SEMANTIC_MARKERS["Missing"] != SEMANTIC_MARKERS["Review"]
    spec = FigureSpec(FigureKind.AGREEMENT_FINGERPRINT, "Annotation Agreement Map")
    assert spec.kind is FigureKind.AGREEMENT_FINGERPRINT

from metaphor_agreement_studio.figures.data import sort_fingerprint_data


def test_fingerprint_sort_modes_keep_occurrences_and_prioritize_disagreement() -> None:
    frame = pd.DataFrame(
        [
            {"unit_id": "u1", "source": "B", "category": "Noun", "lexical_unit": "hand", "occurrence_index": 1, "rater_id": "r1", "requires_review": False},
            {"unit_id": "u1", "source": "B", "category": "Noun", "lexical_unit": "hand", "occurrence_index": 1, "rater_id": "r2", "requires_review": False},
            {"unit_id": "u2", "source": "A", "category": "Verb", "lexical_unit": "move", "occurrence_index": 1, "rater_id": "r1", "requires_review": True},
            {"unit_id": "u2", "source": "A", "category": "Verb", "lexical_unit": "move", "occurrence_index": 1, "rater_id": "r2", "requires_review": True},
        ]
    )
    sorted_frame = sort_fingerprint_data(frame, "Most disagreement first")
    assert sorted_frame.iloc[0]["unit_id"] == "u2"
    assert list(sorted_frame[sorted_frame["unit_id"] == "u2"]["rater_id"]) == ["r1", "r2"]
    category_frame = sort_fingerprint_data(frame, "Grammatical category")
    assert category_frame.iloc[0]["category"] == "Noun"
