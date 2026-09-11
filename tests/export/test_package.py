from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.export.package import ResearchPackageSelection, create_research_package, safe_filename
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "spider", "Noun", "s1", 1),
        LexicalUnit("u2", "hand", "Noun", "s1", 1),
        LexicalUnit("u3", "move", "Verb", "s1", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Braulio"))
    values = {
        ("u1", "r1"): Classification.METAPHOR,
        ("u1", "r2"): Classification.METAPHOR,
        ("u2", "r1"): Classification.NON_METAPHOR,
        ("u2", "r2"): Classification.NON_METAPHOR,
        ("u3", "r1"): Classification.METAPHOR,
        ("u3", "r2"): Classification.NON_METAPHOR,
    }
    anns = tuple(
        Annotation(f"a{i}", u, r, v, "imp", "Sheet1", f"D{i}", v.value, {}, "fixture", ValidationStatus.VALIDATED)
        for i, ((u, r), v) in enumerate(values.items(), start=1)
    )
    return ValidatedDataset("d1", (Source("s1", "Example"),), units, raters, anns, (), ())


def test_safe_filename_removes_paths_controls_and_empty_names() -> None:
    assert safe_filename("../My study / results?.xlsx") == "My_study_results.xlsx"
    assert safe_filename("..") == "artifact"
    assert safe_filename("a b.txt") == "a_b.txt"


def test_research_package_contains_selected_reproducibility_artifacts(tmp_path: Path) -> None:
    ds = dataset()
    bundle = analyze_dataset(ds, AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=20))
    source = tmp_path / "Eduardo.xlsx"
    source.write_bytes(b"original")
    selection = ResearchPackageSelection(
        dataset=ds,
        analysis_bundle=bundle,
        project_name="Metaphor Study",
        dataset_version="v1.0",
        analysis_version="A-001",
        source_files=(source,),
        audit_events=(),
        include_data=True,
        include_statistics=True,
        include_publication=True,
        include_documentation=True,
    )
    package = create_research_package(selection, tmp_path / "research_package.zip")
    with ZipFile(package) as archive:
        names = set(archive.namelist())
    expected = {
        "data/validated_annotations.xlsx",
        "data/annotations_long.csv",
        "statistics/Metaphor_Agreement_Results.xlsx",
        "publication/figure_01_agreement_by_pos.pdf",
        "publication/figure_01_agreement_by_pos.provenance.json",
        "publication/latex/agreement_by_pos.tex",
        "publication/reporting/suggested_reporting.txt",
        "documentation/analysis_settings.json",
        "documentation/validation_summary.txt",
        "reproducibility_manifest.json",
    }
    assert expected <= names


def test_research_package_respects_individual_artifact_selections(tmp_path: Path) -> None:
    ds = dataset()
    bundle = analyze_dataset(ds, AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=20))
    selection = ResearchPackageSelection(
        dataset=ds,
        analysis_bundle=bundle,
        include_data=True,
        include_statistics=False,
        include_publication=False,
        include_documentation=False,
        include_validated_xlsx=True,
        include_long_csv=False,
    )
    package = create_research_package(selection, tmp_path / "selected_package.zip")
    with ZipFile(package) as archive:
        names = set(archive.namelist())
    assert "data/validated_annotations.xlsx" in names
    assert "data/annotations_long.csv" not in names
    assert "statistics/Metaphor_Agreement_Results.xlsx" not in names
    assert "publication/figure_01_agreement_by_pos.pdf" not in names
    assert "documentation/analysis_settings.json" not in names
    assert "reproducibility_manifest.json" in names
