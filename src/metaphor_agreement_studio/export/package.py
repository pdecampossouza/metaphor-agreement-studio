from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from metaphor_agreement_studio import __version__
from metaphor_agreement_studio.common.cache_keys import analysis_config_hash, dataset_content_hash
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.export.datasets import export_long_csv, export_validated_xlsx
from metaphor_agreement_studio.export.manifest import ManifestContext, build_manifest
from metaphor_agreement_studio.export.workbook import export_results_workbook
from metaphor_agreement_studio.figures.data import build_category_agreement_data
from metaphor_agreement_studio.figures.publication import render_publication_figure, save_publication_figure
from metaphor_agreement_studio.figures.types import FigureKind, FigureProvenance, FigureSpec
from metaphor_agreement_studio.persistence.versioning import canonical_analysis_config
from metaphor_agreement_studio.reporting.latex import render_latex_table
from metaphor_agreement_studio.reporting.text import generate_method_summary, suggest_statistical_reporting
from metaphor_agreement_studio.statistics.types import AnalysisBundle


@dataclass(frozen=True, slots=True)
class ResearchPackageSelection:
    dataset: ValidatedDataset
    analysis_bundle: AnalysisBundle
    project_name: str = "Quick Analysis"
    dataset_version: str = "Quick Analysis"
    analysis_version: str = "Current session"
    source_files: tuple[object, ...] = ()
    audit_events: tuple[object, ...] = ()
    include_data: bool = True
    include_statistics: bool = True
    include_publication: bool = True
    include_documentation: bool = True
    include_validated_xlsx: bool | None = None
    include_long_csv: bool | None = None
    include_results_workbook: bool | None = None
    include_publication_figures: bool | None = None
    include_latex_tables: bool | None = None
    include_reporting_text: bool | None = None
    include_validation_summary: bool | None = None
    include_analysis_settings: bool | None = None


def safe_filename(name: str) -> str:
    raw = str(name).replace("\\", " ").replace("/", " ")
    raw = "".join(ch for ch in raw if ord(ch) >= 32 and ord(ch) != 127)
    chars: list[str] = []
    for ch in raw:
        if ch.isascii() and (ch.isalnum() or ch in "._-"):
            chars.append(ch)
        elif ch.isspace():
            chars.append("_")
    clean = re.sub(r"_+", "_", "".join(chars)).strip("._-")
    return clean or "artifact"


def _enabled(specific: bool | None, group: bool) -> bool:
    return group if specific is None else specific


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _validation_summary(selection: ResearchPackageSelection) -> str:
    ds = selection.dataset
    return (
        "Metaphor Agreement Studio — validation summary\n\n"
        f"Dataset: {selection.dataset_version}\n"
        f"Lexical units stored: {len(ds.units)}\n"
        f"Raters: {', '.join(r.display_name for r in ds.raters)}\n"
        f"Validation decisions: {len(ds.validation_decisions)}\n"
        f"Quality notes: {len(ds.quality_notes)}\n"
        "Original source workbooks were not modified by export.\n"
    )


def create_research_package(selection: ResearchPackageSelection, destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    bundle = selection.analysis_bundle
    generated_at = datetime.now(timezone.utc).isoformat()
    analysis_settings = canonical_analysis_config(bundle.config)
    manifest_context = ManifestContext(
        project_name=selection.project_name,
        dataset_version=selection.dataset_version,
        analysis_version=selection.analysis_version,
        source_files=selection.source_files,
        raters=tuple(r.display_name for r in selection.dataset.raters),
        source_groups=tuple(s.display_name for s in selection.dataset.sources),
        analysis_settings=analysis_settings,
        software_version=__version__,
        generated_at=generated_at,
    )
    with tempfile.TemporaryDirectory(prefix="mas-export-") as temp:
        root = Path(temp)
        if _enabled(selection.include_validated_xlsx, selection.include_data):
            export_validated_xlsx(selection.dataset, root / "data" / "validated_annotations.xlsx")
        if _enabled(selection.include_long_csv, selection.include_data):
            export_long_csv(selection.dataset, root / "data" / "annotations_long.csv")
        if _enabled(selection.include_results_workbook, selection.include_statistics):
            export_results_workbook(
                selection.dataset,
                bundle,
                selection.audit_events,
                root / "statistics" / "Metaphor_Agreement_Results.xlsx",
                project_name=selection.project_name,
                dataset_version=selection.dataset_version,
                analysis_version=selection.analysis_version,
            )
        publication_figure = _enabled(selection.include_publication_figures, selection.include_publication)
        latex_tables = _enabled(selection.include_latex_tables, selection.include_publication)
        reporting_text = _enabled(selection.include_reporting_text, selection.include_publication)
        if (publication_figure or latex_tables or reporting_text) and bundle.pairwise:
            first_pair = bundle.pairwise[0]
            pair_ids = (first_pair.rater_a_id, first_pair.rater_b_id)
            figure_data = build_category_agreement_data(bundle, pair_ids)
            spec = FigureSpec(
                FigureKind.AGREEMENT_BY_CATEGORY,
                "Pairwise inter-rater agreement by grammatical category",
                rater_pair=pair_ids,
                size_preset="double-column",
            )
            if publication_figure:
                fig = render_publication_figure(spec, figure_data)
                provenance = FigureProvenance(
                    selection.project_name,
                    selection.dataset_version,
                    selection.analysis_version,
                    tuple(r.display_name for r in selection.dataset.raters),
                    {"rater_pair": list(pair_ids)},
                    __version__,
                    generated_at,
                    dataset_content_hash(selection.dataset),
                    analysis_config_hash(bundle.config),
                )
                save_publication_figure(
                    fig,
                    root / "publication" / "figure_01_agreement_by_pos.pdf",
                    "pdf",
                    provenance=provenance,
                )
            if latex_tables:
                latex = render_latex_table("by_category", bundle, {"rater_pair": pair_ids})
                latex_path = root / "publication" / "latex" / "agreement_by_pos.tex"
                latex_path.parent.mkdir(parents=True, exist_ok=True)
                latex_path.write_text(latex, encoding="utf-8")
            if reporting_text:
                reporting = root / "publication" / "reporting"
                reporting.mkdir(parents=True, exist_ok=True)
                reporting.joinpath("suggested_reporting.txt").write_text(
                    suggest_statistical_reporting(first_pair), encoding="utf-8"
                )
                reporting.joinpath("analysis_method_summary.txt").write_text(
                    generate_method_summary(bundle.config, bundle.counts.raters), encoding="utf-8"
                )
                reporting.joinpath("captions.txt").write_text(
                    "Figure 1. Pairwise inter-rater agreement by grammatical category. Points represent Cohen's Kappa estimates; intervals represent 95% confidence intervals when available.\n",
                    encoding="utf-8",
                )
        if _enabled(selection.include_analysis_settings, selection.include_documentation):
            documentation = root / "documentation"
            documentation.mkdir(parents=True, exist_ok=True)
            _write_json(documentation / "analysis_settings.json", analysis_settings)
        if _enabled(selection.include_validation_summary, selection.include_documentation):
            documentation = root / "documentation"
            documentation.mkdir(parents=True, exist_ok=True)
            documentation.joinpath("validation_summary.txt").write_text(
                _validation_summary(selection), encoding="utf-8"
            )
        _write_json(root / "reproducibility_manifest.json", build_manifest(manifest_context))
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return destination
