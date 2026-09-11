from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from metaphor_agreement_studio.common import cache_keys
from metaphor_agreement_studio.domain.enums import Classification, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.export.package import ResearchPackageSelection, create_research_package
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def _dataset() -> ValidatedDataset:
    units = (
        LexicalUnit("u1", "spider", "Noun", "s1", 1),
        LexicalUnit("u2", "hand", "Noun", "s1", 1),
        LexicalUnit("u3", "move", "Verb", "s1", 1),
        LexicalUnit("u4", "cold", "Adjective", "s1", 1),
    )
    raters = (Rater("r1", "Eduardo"), Rater("r2", "Bráulio"))
    values = {
        ("u1", "r1"): Classification.METAPHOR,
        ("u1", "r2"): Classification.METAPHOR,
        ("u2", "r1"): Classification.NON_METAPHOR,
        ("u2", "r2"): Classification.NON_METAPHOR,
        ("u3", "r1"): Classification.METAPHOR,
        ("u3", "r2"): Classification.NON_METAPHOR,
        ("u4", "r1"): Classification.NON_METAPHOR,
        ("u4", "r2"): Classification.METAPHOR,
    }
    annotations = tuple(
        Annotation(
            f"a{i}",
            unit_id,
            rater_id,
            classification,
            "import-1",
            "Sheet1",
            f"D{i}",
            classification.value,
            {},
            "fixture",
            ValidationStatus.VALIDATED,
        )
        for i, ((unit_id, rater_id), classification) in enumerate(values.items(), start=1)
    )
    return ValidatedDataset(
        "dataset-release-test",
        (Source("s1", "Example"),),
        units,
        raters,
        annotations,
        (),
        (),
    )


def _read_json(archive: ZipFile, name: str) -> dict[str, object]:
    return json.loads(archive.read(name).decode("utf-8"))


def _analytical_manifest(payload: dict[str, object]) -> dict[str, object]:
    transient = {"generated_at", "python_version", "runtime_platform"}
    return {key: value for key, value in payload.items() if key not in transient}


def test_research_exports_are_analytically_reproducible_and_figures_are_hash_linked(
    tmp_path: Path,
) -> None:
    dataset = _dataset()
    config = AnalysisConfig(selected_rater_ids=("r1", "r2"), bootstrap_samples=0)
    bundle = analyze_dataset(dataset, config)

    source = tmp_path / "Eduardo.xlsx"
    source.write_bytes(b"immutable-source")
    assert hasattr(cache_keys, "dataset_content_hash")
    assert hasattr(cache_keys, "analysis_config_hash")
    expected_dataset_hash = cache_keys.dataset_content_hash(dataset)
    expected_config_hash = cache_keys.analysis_config_hash(config)

    packages: list[Path] = []
    for run in ("run-a", "run-b"):
        output_dir = tmp_path / run
        output_dir.mkdir()
        selection = ResearchPackageSelection(
            dataset=dataset,
            analysis_bundle=bundle,
            project_name="Reproducibility Study",
            dataset_version="v1.0",
            analysis_version="A-001",
            source_files=(source,),
            include_data=True,
            include_statistics=True,
            include_publication=True,
            include_documentation=True,
        )
        packages.append(create_research_package(selection, output_dir / "research_package.zip"))

    with ZipFile(packages[0]) as first, ZipFile(packages[1]) as second:
        assert first.read("data/annotations_long.csv") == second.read("data/annotations_long.csv")
        assert first.read("documentation/analysis_settings.json") == second.read(
            "documentation/analysis_settings.json"
        )
        assert _analytical_manifest(_read_json(first, "reproducibility_manifest.json")) == (
            _analytical_manifest(_read_json(second, "reproducibility_manifest.json"))
        )

        for archive in (first, second):
            provenance = _read_json(
                archive, "publication/figure_01_agreement_by_pos.provenance.json"
            )
            assert provenance["dataset_content_hash"] == expected_dataset_hash
            assert provenance["analysis_config_hash"] == expected_config_hash
