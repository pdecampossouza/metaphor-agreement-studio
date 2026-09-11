from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from metaphor_agreement_studio.figures.provenance import write_provenance_sidecar
from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureProvenance, FigureSpec

PUBLICATION_SIZES: dict[str, tuple[float, float]] = {
    "single-column": (3.35, 2.70),
    "double-column": (7.00, 4.20),
    "presentation": (10.00, 5.625),
}


def _new_figure(spec: FigureSpec):
    size = PUBLICATION_SIZES.get(spec.size_preset, PUBLICATION_SIZES["double-column"])
    fig, ax = plt.subplots(figsize=size, constrained_layout=True)
    ax.set_title(spec.title, loc="left", fontsize=10, fontweight="semibold")
    if spec.subtitle:
        ax.text(0, 1.01, spec.subtitle, transform=ax.transAxes, fontsize=8, va="bottom")
    return fig, ax


def _point_interval(ax, frame, label_column: str) -> None:
    frame = frame.reset_index(drop=True)
    y = np.arange(len(frame))
    for idx, row in frame.iterrows():
        estimate = row.get("estimate")
        label = row[label_column]
        n = row.get("n", "")
        if estimate is None or (isinstance(estimate, float) and math.isnan(estimate)):
            ax.plot(0, idx, marker="o", markerfacecolor="none", linestyle="None")
            ax.text(0.04, idx, f"descriptive only · n={n}", va="center", fontsize=7)
            continue
        lo = row.get("ci_low")
        hi = row.get("ci_high")
        if lo is not None and hi is not None and not (pd_isna(lo) or pd_isna(hi)):
            ax.hlines(idx, lo, hi, linewidth=1.1)
        ax.plot(estimate, idx, marker="o", linestyle="None")
        ax.text(min(0.96, estimate + 0.03), idx, f"n={n}", va="center", fontsize=7)
    ax.set_yticks(y, frame[label_column].tolist())
    ax.set_xlim(-1, 1)
    ax.axvline(0, linewidth=0.7, linestyle="--")
    ax.set_xlabel("Cohen's κ")
    ax.grid(axis="x", linewidth=0.35, alpha=0.35)


def pd_isna(value) -> bool:
    try:
        return bool(np.isnan(value))
    except TypeError:
        return value is None


def _pairwise_matrix(ax, frame) -> None:
    raters = list(dict.fromkeys(frame["rater_a"].tolist() + frame["rater_b"].tolist()))
    matrix = np.full((len(raters), len(raters)), np.nan)
    pos = {rater: i for i, rater in enumerate(raters)}
    for row in frame.itertuples(index=False):
        if row.rater_a == row.rater_b or pd_isna(row.estimate):
            continue
        matrix[pos[row.rater_a], pos[row.rater_b]] = row.estimate
    im = ax.imshow(matrix, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(raters)), raters, rotation=45, ha="right")
    ax.set_yticks(range(len(raters)), raters)
    for i, a in enumerate(raters):
        for j, b in enumerate(raters):
            text = "—" if a == b or np.isnan(matrix[i, j]) else f"{matrix[i, j]:.2f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=8)
    ax.figure.colorbar(im, ax=ax, label="Cohen's κ", fraction=0.05, pad=0.03)


def _fingerprint(ax, frame) -> None:
    if frame.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    units = list(dict.fromkeys(frame["unit_id"].tolist()))
    raters = list(dict.fromkeys(frame["rater"].tolist()))
    ux = {unit: i for i, unit in enumerate(units)}
    rx = {rater: i for i, rater in enumerate(raters)}
    labels = {}
    for row in frame.itertuples(index=False):
        labels.setdefault(row.unit_id, f"{row.lexical_unit} · {row.source}")
        marker = {"Metaphor": "o", "Non-metaphor": "x", "Missing": "o"}.get(row.classification, "D")
        fillstyle = "none" if row.classification == "Missing" else "full"
        ax.plot(rx[row.rater], ux[row.unit_id], marker=marker, fillstyle=fillstyle, linestyle="None", markersize=5)
        if row.requires_review:
            ax.plot(rx[row.rater], ux[row.unit_id], marker="D", fillstyle="none", linestyle="None", markersize=7)
    ax.set_xticks(range(len(raters)), raters, rotation=30, ha="right")
    if len(units) <= 40:
        ax.set_yticks(range(len(units)), [labels[u] for u in units], fontsize=6)
    else:
        ax.set_yticks([])
        ax.set_ylabel(f"{len(units)} lexical occurrences")
    ax.invert_yaxis()
    ax.grid(axis="x", linewidth=0.3, alpha=0.3)


def _simple_bar(ax, frame, x: str, y: str, y_label: str, *, hatch: bool = False) -> None:
    bars = ax.bar(range(len(frame)), frame[y].fillna(0).tolist())
    if hatch:
        patterns = ["/", "x", ".", "-"]
        for i, bar in enumerate(bars):
            bar.set_hatch(patterns[i % len(patterns)])
    ax.set_xticks(range(len(frame)), frame[x].astype(str).tolist(), rotation=30, ha="right")
    ax.set_ylabel(y_label)
    ax.grid(axis="y", linewidth=0.35, alpha=0.35)


def _specific_agreement(ax, frame) -> None:
    pairs = list(dict.fromkeys(f"{a} × {b}" for a, b in zip(frame["rater_a"], frame["rater_b"], strict=True)))
    pair_pos = {pair: i for i, pair in enumerate(pairs)}
    offsets = {"Metaphor": -0.10, "Non-metaphor": 0.10}
    markers = {"Metaphor": "o", "Non-metaphor": "x"}
    for classification in ("Metaphor", "Non-metaphor"):
        subset = frame[frame["classification"] == classification]
        if subset.empty:
            continue
        xs = [pair_pos[f"{a} × {b}"] + offsets[classification] for a, b in zip(subset["rater_a"], subset["rater_b"], strict=True)]
        ax.plot(xs, subset["estimate"], marker=markers[classification], linestyle="None", label=classification)
    ax.set_xticks(range(len(pairs)), pairs, rotation=30, ha="right")
    ax.set_ylabel("Specific agreement")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False)
    ax.grid(axis="y", linewidth=0.35, alpha=0.35)


def render_publication_figure(spec: FigureSpec, data: FigureDataset):
    fig, ax = _new_figure(spec)
    kind = spec.kind
    frame = data.frame
    if kind is FigureKind.AGREEMENT_BY_CATEGORY:
        _point_interval(ax, frame, "category")
    elif kind is FigureKind.SOURCE_COMPARISON:
        _point_interval(ax, frame, "source")
    elif kind is FigureKind.PAIRWISE_KAPPA_MATRIX:
        _pairwise_matrix(ax, frame)
    elif kind is FigureKind.AGREEMENT_FINGERPRINT:
        _fingerprint(ax, frame)
    elif kind is FigureKind.AGREEMENT_VS_SAMPLE_SIZE:
        ax.scatter(frame["n"], frame["raw_agreement"], marker="o")
        for row in frame.itertuples(index=False):
            ax.annotate(row.category, (row.n, row.raw_agreement), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel("Lexical units (N)")
        ax.set_ylabel("Raw agreement")
        ax.set_ylim(0, 1.05)
    elif kind is FigureKind.METAPHOR_RATE_BY_RATER:
        _simple_bar(ax, frame, "rater", "rate", "Metaphor classification rate", hatch=True)
        ax.set_ylim(0, 1.05)
    elif kind is FigureKind.DISAGREEMENT_BY_CATEGORY:
        _simple_bar(ax, frame, "category", "rate", "Disagreement rate", hatch=True)
        ax.set_ylim(0, 1.05)
    elif kind is FigureKind.RATER_DIVERGENCE:
        ax.plot(frame["mean_pairwise_kappa"], frame["rater"], marker="o", linestyle="None")
        ax.set_xlabel("Mean pairwise Cohen's κ")
        ax.set_xlim(-1, 1)
    elif kind is FigureKind.MULTI_RATER_PATTERNS:
        _simple_bar(ax, frame, "pattern", "count", "Lexical units", hatch=True)
    elif kind is FigureKind.SPECIFIC_AGREEMENT:
        _specific_agreement(ax, frame)
    elif kind is FigureKind.REVIEW_DENSITY:
        sizes = 25 + 350 * frame["rate"] if not frame.empty else []
        ax.scatter(frame["category"], frame["source"], s=sizes, marker="D", facecolors="none")
        for row in frame.itertuples(index=False):
            ax.annotate(f"{row.disagreement_cases}/{row.n}", (row.category, row.source), fontsize=6, xytext=(3, 2), textcoords="offset points")
        ax.set_xlabel("Grammatical category")
        ax.set_ylabel("Source")
    else:
        raise ValueError(f"Unsupported publication figure kind: {kind}")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return fig


def save_publication_figure(
    fig,
    destination: Path,
    format: str,
    dpi: int = 300,
    *,
    provenance: FigureProvenance | None = None,
    transparent: bool = False,
) -> Path:
    destination = Path(destination)
    format = format.lower().lstrip(".")
    if format not in {"png", "svg", "pdf"}:
        raise ValueError("Publication figures support PNG, SVG, and PDF only")
    if format == "png" and dpi not in {300, 600}:
        raise ValueError("Publication PNG dpi must be 300 or 600")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        destination,
        format=format,
        dpi=dpi if format == "png" else None,
        transparent=transparent,
        facecolor="none" if transparent else "white",
        bbox_inches="tight",
    )
    if provenance is not None:
        write_provenance_sidecar(destination, provenance)
    return destination
