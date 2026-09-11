from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from metaphor_agreement_studio.figures.types import FigureProvenance


def provenance_sidecar_path(figure_path: Path) -> Path:
    figure_path = Path(figure_path)
    return figure_path.with_name(f"{figure_path.stem}.provenance.json")


def write_provenance_sidecar(figure_path: Path, provenance: FigureProvenance) -> Path:
    sidecar = provenance_sidecar_path(figure_path)
    sidecar.write_text(
        json.dumps(asdict(provenance), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return sidecar
