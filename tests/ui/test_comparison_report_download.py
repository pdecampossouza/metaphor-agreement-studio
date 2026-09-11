from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def _dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "hand", "Noun", "s1", 1),
        LexicalUnit("u2", "fall", "Verb", "s1", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"))
    annotations = (
        Annotation("a1", "u1", "r1", Classification.METAPHOR, "imp", "S", "A1", "M", {}, "fixture", ValidationStatus.VALIDATED),
        Annotation("a2", "u2", "r1", Classification.NON_METAPHOR, "imp", "S", "A2", "N", {}, "fixture", ValidationStatus.VALIDATED),
        Annotation("a3", "u1", "r2", Classification.METAPHOR, "imp", "S", "B1", "M", {}, "fixture", ValidationStatus.VALIDATED),
        Annotation("a4", "u2", "r2", Classification.METAPHOR, "imp", "S", "B2", "M", {}, "fixture", ValidationStatus.VALIDATED),
    )
    return ValidatedDataset("d", (Source("s1", "Song A"),), units, raters, annotations, (), ())


def test_comparison_report_download_uses_current_project_versions() -> None:
    from metaphor_agreement_studio.ui.pages.statistics import build_comparison_report_download

    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0))
    state = {
        "project_name": "Braulio Doctoral Study",
        "dataset_version": "v3.0",
        "analysis_version": "A-007",
    }

    filename, payload = build_comparison_report_download(dataset, bundle, state)

    assert filename == "Braulio_Doctoral_Study_A-007_comparison_report.pdf"
    assert payload.startswith(b"%PDF-")
