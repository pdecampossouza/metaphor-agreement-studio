from __future__ import annotations

from pathlib import Path
from time import perf_counter

from metaphor_agreement_studio.common.cache_keys import analysis_cache_key, workbook_content_cache_key
from metaphor_agreement_studio.domain.enums import Classification, SourceType, ValidationStatus
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.domain.models import Annotation, LexicalUnit, Rater, Source
from metaphor_agreement_studio.statistics.engine import analyze_dataset
from metaphor_agreement_studio.statistics.types import AnalysisConfig


def test_workbook_cache_key_depends_on_bytes_not_path(tmp_path: Path) -> None:
    first = tmp_path / "a.xlsx"
    second = tmp_path / "nested" / "b.xlsx"
    second.parent.mkdir()
    first.write_bytes(b"same workbook bytes")
    second.write_bytes(b"same workbook bytes")

    assert workbook_content_cache_key(first) == workbook_content_cache_key(second)
    second.write_bytes(b"changed workbook bytes")
    assert workbook_content_cache_key(first) != workbook_content_cache_key(second)


def _small_dataset(classification: Classification = Classification.METAPHOR) -> ValidatedDataset:
    source = Source("s1", "Source", SourceType.TABLE)
    unit = LexicalUnit("u1", "hand", "Noun", "s1", 1)
    rater = Rater("r1", "Rater 1")
    annotation = Annotation(
        "a1",
        "u1",
        "r1",
        classification,
        "imp1",
        "Sheet1",
        "D2",
        None,
        {},
        "test",
        ValidationStatus.VALIDATED,
    )
    return ValidatedDataset("d1", (source,), (unit,), (rater,), (annotation,), (), ())


def test_analysis_cache_key_changes_with_dataset_or_config() -> None:
    dataset = _small_dataset()
    config = AnalysisConfig(bootstrap_samples=0)
    assert analysis_cache_key(dataset, config) == analysis_cache_key(dataset, config)
    assert analysis_cache_key(dataset, config) != analysis_cache_key(
        _small_dataset(Classification.NON_METAPHOR), config
    )
    assert analysis_cache_key(dataset, config) != analysis_cache_key(
        dataset, AnalysisConfig(bootstrap_samples=0, selected_categories=("Noun",))
    )


def test_ten_thousand_units_five_raters_analysis_smoke() -> None:
    source = Source("s1", "Large Source", SourceType.TABLE)
    raters = tuple(Rater(f"r{i}", f"Rater {i}") for i in range(5))
    units = tuple(
        LexicalUnit(f"u{i}", f"unit-{i}", "Noun" if i % 2 else "Verb", "s1", 1)
        for i in range(10_000)
    )
    annotations = tuple(
        Annotation(
            f"a-{i}-{r}",
            f"u{i}",
            f"r{r}",
            Classification.METAPHOR if (i + r) % 3 else Classification.NON_METAPHOR,
            "imp-large",
            "Sheet1",
            f"D{i + 2}",
            None,
            {},
            "synthetic performance smoke",
            ValidationStatus.VALIDATED,
        )
        for i in range(10_000)
        for r in range(5)
    )
    dataset = ValidatedDataset(
        "large",
        (source,),
        units,
        raters,
        annotations,
        (),
        (),
    )

    started = perf_counter()
    bundle = analyze_dataset(dataset, AnalysisConfig(bootstrap_samples=0))
    elapsed = perf_counter() - started

    assert bundle.counts.lexical_units == 10_000
    assert bundle.counts.raters == 5
    assert len(bundle.pairwise) == 10
    assert elapsed < 30.0


def test_streamlit_workspaces_use_content_hash_cache_wrappers() -> None:
    validation_text = Path("src/metaphor_agreement_studio/ui/pages/validation.py").read_text(encoding="utf-8")
    assert "inspect_workbook_cached" in validation_text
    for name in (
        "agreement.py",
        "categories.py",
        "sources.py",
        "rater_explorer.py",
        "statistics.py",
        "figures.py",
        "reporting.py",
        "export_center.py",
    ):
        text = Path("src/metaphor_agreement_studio/ui/pages", name).read_text(encoding="utf-8")
        assert "analyze_dataset_cached" in text, name
