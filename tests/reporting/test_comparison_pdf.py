from __future__ import annotations

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def _dataset() -> ValidatedDataset:
    units = tuple(
        LexicalUnit(f"u{i}", word, pos, "s1", 1)
        for i, (word, pos) in enumerate(
            [("a", "Noun"), ("b", "Noun"), ("c", "Verb"), ("d", "Verb")],
            start=1,
        )
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"), Rater("r3", "Sofia"))
    values = {
        "r1": [1, 0, 1, 0],
        "r2": [1, 0, 0, 0],
        "r3": [1, 1, 0, 0],
    }
    annotations = []
    index = 0
    for rater_id, row in values.items():
        for unit, value in zip(units, row, strict=True):
            index += 1
            classification = Classification.METAPHOR if value else Classification.NON_METAPHOR
            annotations.append(
                Annotation(
                    annotation_id=f"a{index}",
                    unit_id=unit.unit_id,
                    rater_id=rater_id,
                    classification=classification,
                    import_id="imp",
                    original_sheet="Sheet1",
                    original_cell=f"A{index}",
                    original_raw_value=classification.value,
                    original_style={},
                    detection_method="fixture",
                    validation_status=ValidationStatus.VALIDATED,
                )
            )
    return ValidatedDataset(
        dataset_id="report_dataset",
        sources=(Source("s1", "Example"),),
        units=units,
        raters=raters,
        annotations=tuple(annotations),
        quality_notes=(),
        validation_decisions=(),
    )


def test_two_rater_report_uses_cohen_kappa_as_primary_metric() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import report_analysis_design

    bundle = analyze_dataset(
        _dataset(),
        AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0),
    )

    design = report_analysis_design(bundle)

    assert design.primary_agreement_metric == "Cohen's Kappa"
    assert "two selected raters" in design.rationale


def test_two_rater_report_explains_cochran_q_and_mcnemar_relationship() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import report_analysis_design

    bundle = analyze_dataset(
        _dataset(),
        AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0),
    )

    design = report_analysis_design(bundle)

    assert "not an agreement coefficient" in design.classification_tendency_note
    assert "McNemar" in design.classification_tendency_note


def test_multirater_report_uses_fleiss_and_retains_pairwise_cohen() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import report_analysis_design

    bundle = analyze_dataset(_dataset(), AnalysisConfig(bootstrap_samples=0))
    design = report_analysis_design(bundle)

    assert design.primary_agreement_metric == "Fleiss' Kappa"
    assert "pairwise Cohen's Kappa" in design.rationale


def test_comparison_report_builds_pdf_bytes_with_reproducible_filename() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import (
        ComparisonReportMetadata,
        build_comparison_report_pdf,
        comparison_report_filename,
    )

    dataset = _dataset()
    bundle = analyze_dataset(
        dataset,
        AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0),
    )
    metadata = ComparisonReportMetadata(
        project_name="Doctoral Study",
        dataset_version="v1.0",
        analysis_version="A-004",
        generated_at="2026-09-06T11:45:00+01:00",
    )

    payload = build_comparison_report_pdf(dataset, bundle, metadata)

    assert payload.startswith(b"%PDF-")
    assert len(payload) > 10_000
    assert comparison_report_filename(metadata) == "Doctoral_Study_A-004_comparison_report.pdf"


def test_analysis_design_summary_is_plain_text_for_pdf_rendering() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import analysis_design_summary_text

    bundle = analyze_dataset(
        _dataset(),
        AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0),
    )

    summary = analysis_design_summary_text(bundle)

    assert summary.startswith("Cohen's Kappa is the primary agreement statistic")
    assert "<" not in summary and ">" not in summary


def test_multirater_pdf_reports_fleiss_within_categories_and_sources() -> None:
    from io import BytesIO

    from pypdf import PdfReader

    from metaphor_agreement_studio.reporting.comparison_pdf import build_comparison_report_pdf

    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    payload = build_comparison_report_pdf(dataset, bundle)
    page_texts = [page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages]

    category_page = next(text for text in page_texts if "Agreement by grammatical category" in text)
    source_page = next(text for text in page_texts if "Agreement by source" in text)
    assert "Fleiss' Kappa" in category_page
    assert "Fleiss' Kappa" in source_page


def test_multirater_analysis_design_says_grouped_fleiss_is_repeated_by_pos_and_source() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import report_analysis_design

    bundle = analyze_dataset(_dataset(), AnalysisConfig(bootstrap_samples=0))
    design = report_analysis_design(bundle)

    assert "grammatical" in design.rationale.lower()
    assert "source" in design.rationale.lower()


def test_pdf_reports_cochran_q_within_categories_and_sources() -> None:
    from io import BytesIO

    from pypdf import PdfReader

    from metaphor_agreement_studio.reporting.comparison_pdf import build_comparison_report_pdf

    dataset = _dataset()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    payload = build_comparison_report_pdf(dataset, bundle)
    page_texts = [page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages]

    category_page = next(text for text in page_texts if "Agreement by grammatical category" in text)
    source_page = next(text for text in page_texts if "Agreement by source" in text)
    assert "Cochran's Q" in category_page
    assert "Cochran's Q" in source_page


def test_two_rater_analysis_design_states_protocol_is_repeated_by_pos_and_source() -> None:
    from metaphor_agreement_studio.reporting.comparison_pdf import report_analysis_design

    bundle = analyze_dataset(
        _dataset(),
        AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0),
    )
    design = report_analysis_design(bundle)

    assert "grammatical" in design.rationale.lower()
    assert "source" in design.rationale.lower()
