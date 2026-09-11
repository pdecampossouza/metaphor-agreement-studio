from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from metaphor_agreement_studio.statistics.types import AnalysisBundle, EstimateStatus

_TEMPLATE_DIR = Path(__file__).with_name("templates")
_ENV = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), undefined=StrictUndefined, autoescape=False)

_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value: object) -> str:
    text = str(value)
    return "".join(_REPLACEMENTS.get(char, char) for char in text)


def _metric(value: float | None, status: EstimateStatus | None = None, digits: int = 2) -> str:
    if value is None:
        if status is EstimateStatus.NOT_ESTIMABLE_NO_VARIATION:
            return "Not estimable"
        if status is EstimateStatus.DESCRIPTIVE_ONLY:
            return "Descriptive only"
        return "NA"
    return f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    return "NA" if value is None else f"{value * 100:.1f}\\%"


def _p(value: float | None) -> str:
    if value is None:
        return "NA"
    return "$< .001$" if value < 0.001 else f"{value:.3f}"


def _pair_for(group, pair_ids: tuple[str, str]):
    target = frozenset(pair_ids)
    return next((p for p in group.pairwise if frozenset((p.rater_a_id, p.rater_b_id)) == target), None)


def render_latex_table(
    table_kind: str,
    analysis_bundle: AnalysisBundle,
    selection: Mapping[str, object] | None = None,
) -> str:
    selection = selection or {}
    pair_ids = tuple(selection.get("rater_pair", ()))
    rows: list[str] = []
    if table_kind in {"by_category", "by_source"}:
        groups = analysis_bundle.by_category if table_kind == "by_category" else analysis_bundle.by_source
        if len(pair_ids) != 2 and analysis_bundle.pairwise:
            first = analysis_bundle.pairwise[0]
            pair_ids = (first.rater_a_id, first.rater_b_id)
        for group in groups:
            pair = _pair_for(group, pair_ids) if len(pair_ids) == 2 else None
            q = group.cochran_q
            rows.append(
                " & ".join(
                    [
                        escape_latex(group.display_name),
                        str(group.lexical_unit_count),
                        _pct(pair.raw_agreement.value) if pair else "NA",
                        _metric(pair.kappa.value, pair.kappa.status) if pair else "NA",
                        _p(q.p_value) if q else "NA",
                    ]
                )
            )
        caption = "Inter-rater agreement by grammatical category" if table_kind == "by_category" else "Inter-rater agreement by source group"
        header = "Group & N & Raw agreement & Cohen's $\\kappa$ & Cochran Q $p$"
        column_spec = "lrrrr"
    elif table_kind == "pairwise":
        for pair in analysis_bundle.pairwise:
            rows.append(
                " & ".join(
                    [
                        escape_latex(f"{pair.rater_a_id} × {pair.rater_b_id}"),
                        str(pair.kappa.effective_n),
                        _pct(pair.raw_agreement.value),
                        _metric(pair.kappa.value, pair.kappa.status),
                    ]
                )
            )
        caption = "Pairwise inter-rater agreement"
        header = "Rater pair & N & Raw agreement & Cohen's $\\kappa$"
        column_spec = "lrrr"
    elif table_kind == "overall":
        q = analysis_bundle.cochran_q
        rows.append(
            " & ".join(
                [
                    str(analysis_bundle.counts.lexical_units),
                    str(analysis_bundle.counts.raters),
                    "NA" if q is None or q.q is None else f"{q.q:.2f}",
                    "NA" if q is None else _p(q.p_value),
                ]
            )
        )
        caption = "Overall annotation study summary"
        header = "Lexical units & Raters & Cochran's Q & $p$"
        column_spec = "rrrr"
    else:
        raise ValueError(f"Unsupported LaTeX table kind: {table_kind}")
    template = _ENV.get_template("table.tex.j2")
    return template.render(
        caption=escape_latex(caption),
        column_spec=column_spec,
        header=header,
        rows=rows,
    )


def _safe_latex_label(label: str) -> str:
    label = re.sub(r"[^A-Za-z0-9:.-]+", "-", label.strip())
    return label.strip(".-") or "fig:figure"


def render_figure_latex(filename: str, caption: str, label: str) -> str:
    template = _ENV.get_template("figure.tex.j2")
    safe_filename = str(filename).replace("\\", "/").split("/")[-1]
    return template.render(
        filename=escape_latex(safe_filename),
        caption=escape_latex(caption),
        label=_safe_latex_label(label),
    )
