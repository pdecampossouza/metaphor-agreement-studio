from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import re
from typing import Iterable

from metaphor_agreement_studio import __version__
from metaphor_agreement_studio.common.cache_keys import analysis_config_hash, dataset_content_hash
from metaphor_agreement_studio.domain.enums import Classification
from metaphor_agreement_studio.domain.imports import ValidatedDataset
from metaphor_agreement_studio.review.service import build_review_cases
from metaphor_agreement_studio.review.types import ReviewStatus
from metaphor_agreement_studio.statistics.types import (
    AnalysisBundle,
    AnalysisPerspective,
    CategoryAssociationAnalysis,
    GroupResult,
    MetricResult,
)


@dataclass(frozen=True, slots=True)
class ReportAnalysisDesign:
    selected_rater_count: int
    primary_agreement_metric: str
    rationale: str
    classification_tendency_note: str


@dataclass(frozen=True, slots=True)
class ComparisonReportMetadata:
    project_name: str = "Quick Analysis"
    dataset_version: str | None = None
    analysis_version: str | None = None
    generated_at: str | None = None
    software_version: str = __version__


def report_analysis_design(bundle: AnalysisBundle) -> ReportAnalysisDesign:
    rater_count = bundle.counts.raters
    if rater_count == 2:
        return ReportAnalysisDesign(
            selected_rater_count=2,
            primary_agreement_metric="Cohen's Kappa",
            rationale=(
                "With two selected raters, Cohen's Kappa is the primary chance-corrected "
                "agreement coefficient. Cohen's Kappa and Cochran's Q are repeated within "
                "grammatical categories and source tables so the two-rater protocol is applied "
                "at every analytical level."
            ),
            classification_tendency_note=(
                "Cochran's Q is not an agreement coefficient. With two paired binary raters, "
                "it addresses the same marginal-homogeneity question conventionally tested with "
                "McNemar's test, which is also reported for pairwise tendency comparison."
            ),
        )
    return ReportAnalysisDesign(
        selected_rater_count=rater_count,
        primary_agreement_metric="Fleiss' Kappa",
        rationale=(
            "With three or more selected raters, Fleiss' Kappa is the primary global "
            "chance-corrected agreement coefficient; pairwise Cohen's Kappa remains available "
            "for rater-by-rater comparisons. Fleiss' Kappa is also repeated within grammatical "
            "categories and source tables so the multi-rater protocol is applied at every analytical level."
        ),
        classification_tendency_note=(
            "Cochran's Q is not an agreement coefficient. It tests whether the selected raters "
            "differ systematically in their tendency to classify units as metaphorical."
        ),
    )


def analysis_design_summary_text(bundle: AnalysisBundle) -> str:
    design = report_analysis_design(bundle)
    return (
        f"{design.primary_agreement_metric} is the primary agreement statistic for this report. "
        f"{design.rationale}"
    )


def comparison_report_filename(metadata: ComparisonReportMetadata) -> str:
    project = re.sub(r"[^A-Za-z0-9._-]+", "_", metadata.project_name.strip()).strip("_")
    project = project or "Metaphor_Agreement_Studio"
    analysis = metadata.analysis_version or "analysis"
    return f"{project}_{analysis}_comparison_report.pdf"


def _metric_text(metric: MetricResult | None, *, percent: bool = False, digits: int = 3) -> str:
    if metric is None or metric.value is None:
        return "Not estimable"
    if percent:
        return f"{metric.value * 100:.1f}%"
    return f"{metric.value:.{digits}f}"


def _p_text(value: float | None) -> str:
    if value is None:
        return "Not estimable"
    if value < 0.001:
        return "< .001"
    return f"{value:.3f}"


def _exact_p_text(value: float | None) -> str:
    if value is None:
        return "Not estimable"
    return f"{value:.6f}"


def _ci_text(metric: MetricResult) -> str:
    if metric.ci_low is None or metric.ci_high is None:
        return "-"
    return f"[{metric.ci_low:.3f}, {metric.ci_high:.3f}]"


def _selected_rater_ids(dataset: ValidatedDataset, bundle: AnalysisBundle) -> tuple[str, ...]:
    if bundle.config.selected_rater_ids:
        selected = set(bundle.config.selected_rater_ids)
        return tuple(r.rater_id for r in dataset.raters if r.rater_id in selected)
    return tuple(r.rater_id for r in dataset.raters)


def _selected_source_ids(dataset: ValidatedDataset, bundle: AnalysisBundle) -> tuple[str, ...]:
    if bundle.config.selected_source_ids:
        selected = set(bundle.config.selected_source_ids)
        return tuple(s.source_id for s in dataset.sources if s.source_id in selected)
    return tuple(s.source_id for s in dataset.sources if not s.is_aggregate)


def _selected_unit_ids(dataset: ValidatedDataset, bundle: AnalysisBundle) -> tuple[str, ...]:
    sources = set(_selected_source_ids(dataset, bundle))
    categories = set(bundle.config.selected_categories)
    return tuple(
        unit.unit_id
        for unit in dataset.units
        if unit.source_id in sources and (not categories or unit.grammatical_category in categories)
    )


def _mean_pairwise_agreement(group: GroupResult) -> float | None:
    values = [pair.raw_agreement.value for pair in group.pairwise if pair.raw_agreement.value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _group_chart(groups: Iterable[GroupResult], title: str) -> BytesIO | None:
    import matplotlib.pyplot as plt

    rows = [(group.display_name, _mean_pairwise_agreement(group)) for group in groups]
    rows = [(name, value) for name, value in rows if value is not None]
    if not rows:
        return None
    labels = [name for name, _ in rows]
    values = [float(value) * 100 for _, value in rows]
    height = max(2.8, 0.55 * len(rows) + 1.5)
    fig, ax = plt.subplots(figsize=(7.2, height))
    bars = ax.barh(labels, values)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Mean pairwise observed agreement (%)")
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=0.18)
    ax.invert_yaxis()
    for bar, value in zip(bars, values, strict=True):
        ax.text(min(value + 1.2, 96), bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", fontsize=9)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _proportional_report_image(
    image_source: BytesIO,
    *,
    max_width: float,
    max_height: float,
):
    """Create a ReportLab image constrained without distorting its aspect ratio."""
    from reportlab.platypus import Image

    image_source.seek(0)
    image = Image(image_source)
    source_width = float(image.imageWidth)
    source_height = float(image.imageHeight)
    if source_width <= 0 or source_height <= 0:
        return image

    scale = min(max_width / source_width, max_height / source_height)
    image.drawWidth = source_width * scale
    image.drawHeight = source_height * scale
    return image


def _disagreement_chart(dataset: ValidatedDataset, bundle: AnalysisBundle) -> BytesIO | None:
    import matplotlib.pyplot as plt

    unit_ids = _selected_unit_ids(dataset, bundle)
    cases = build_review_cases(dataset, selected_raters=_selected_rater_ids(dataset, bundle), unit_ids=unit_ids)
    disagreements = [case for case in cases if case.status is ReviewStatus.DISAGREEMENT]
    counts = Counter(case.grammatical_category for case in disagreements)
    if not counts:
        return None
    labels = sorted(counts)
    values = [counts[label] for label in labels]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    bars = ax.bar(labels, values)
    ax.set_ylabel("Disagreement cases")
    ax.set_title("Disagreement cases by grammatical category", loc="left", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.18)
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.15, str(value), ha="center", fontsize=9)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _primary_metric(bundle: AnalysisBundle) -> MetricResult | None:
    if bundle.counts.raters == 2:
        return bundle.pairwise[0].kappa if bundle.pairwise else None
    for metric in bundle.overall_multirater:
        if metric.metric == "fleiss_kappa":
            return metric
    return None


def _mean_raw_agreement(bundle: AnalysisBundle) -> str:
    values = [pair.raw_agreement.value for pair in bundle.pairwise if pair.raw_agreement.value is not None]
    if not values:
        return "Not estimable"
    return f"{sum(values) / len(values) * 100:.1f}%"


def _perspective_label(bundle: AnalysisBundle) -> str:
    return {
        AnalysisPerspective.NO_REFERENCE: "No reference",
        AnalysisPerspective.REFERENCE_RATER: "Reference rater",
        AnalysisPerspective.EXPERT_BENCHMARK: "Expert benchmark",
    }[bundle.config.analysis_perspective]


def build_comparison_report_pdf(
    dataset: ValidatedDataset,
    bundle: AnalysisBundle,
    metadata: ComparisonReportMetadata | None = None,
    *,
    category_association: CategoryAssociationAnalysis | None = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    metadata = metadata or ComparisonReportMetadata()
    if category_association is None:
        from metaphor_agreement_studio.statistics.category_association import (
            analyze_grammatical_category_association,
        )

        category_association = analyze_grammatical_category_association(dataset, bundle.config)
    generated_at = metadata.generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    design = report_analysis_design(bundle)
    names = {r.rater_id: r.display_name for r in dataset.raters}
    source_names = {s.source_id: s.display_name for s in dataset.sources}
    selected_raters = _selected_rater_ids(dataset, bundle)
    selected_sources = _selected_source_ids(dataset, bundle)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Metaphor Agreement Studio - Inter-rater Comparison Report",
        author="Metaphor Agreement Studio",
    )
    stylesheet = getSampleStyleSheet()
    accent = colors.HexColor("#294B63")
    dark = colors.HexColor("#20272D")
    muted = colors.HexColor("#5F6B73")
    pale = colors.HexColor("#EEF2F4")
    border = colors.HexColor("#CBD3D8")
    styles = {
        "title": ParagraphStyle("MAS Title", parent=stylesheet["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=dark, spaceAfter=5 * mm),
        "subtitle": ParagraphStyle("MAS Subtitle", parent=stylesheet["Normal"], fontName="Helvetica", fontSize=11, leading=15, textColor=muted, spaceAfter=8 * mm),
        "h1": ParagraphStyle("MAS H1", parent=stylesheet["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=dark, spaceBefore=4 * mm, spaceAfter=3 * mm),
        "h2": ParagraphStyle("MAS H2", parent=stylesheet["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=accent, spaceBefore=3 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("MAS Body", parent=stylesheet["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13.2, textColor=dark, spaceAfter=2.2 * mm),
        "small": ParagraphStyle("MAS Small", parent=stylesheet["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10.5, textColor=muted),
        "table_header": ParagraphStyle("MAS Table Header", parent=stylesheet["BodyText"], fontName="Helvetica-Bold", fontSize=7.8, leading=10.5, textColor=colors.white),
        "callout": ParagraphStyle("MAS Callout", parent=stylesheet["BodyText"], fontName="Helvetica", fontSize=9.3, leading=13, textColor=dark, backColor=pale, borderColor=border, borderWidth=0.5, borderPadding=8, spaceBefore=2 * mm, spaceAfter=4 * mm),
        "center": ParagraphStyle("MAS Center", parent=stylesheet["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=15, textColor=accent),
        "left": ParagraphStyle("MAS Left", parent=stylesheet["BodyText"], alignment=TA_LEFT, fontName="Helvetica", fontSize=8.5, leading=11.5),
    }

    def P(text: object, style: str = "body") -> Paragraph:
        safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, styles[style])

    def table(data, widths, *, header=True, font_size=7.8):
        if header and data:
            header_row = [
                Paragraph(
                    cell.getPlainText() if isinstance(cell, Paragraph) else str(cell),
                    styles["table_header"],
                )
                for cell in data[0]
            ]
            data = [header_row, *data[1:]]
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.35, border),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ])
        for row in range(1 if header else 0, len(data)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F8FAFB")))
        t.setStyle(TableStyle(commands))
        return t

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(18 * mm, 8 * mm, "Metaphor Agreement Studio - Inter-rater Comparison Report")
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    story = []
    story.append(P("Metaphor Agreement Studio", "title"))
    story.append(P("Inter-rater Comparison Report", "center"))
    story.append(Spacer(1, 3 * mm))
    story.append(P("A reproducible comparison report for lexical metaphor annotation.", "subtitle"))

    meta_rows = [
        [P("Project", "small"), P(metadata.project_name, "left"), P("Generated", "small"), P(generated_at, "left")],
        [P("Dataset version", "small"), P(metadata.dataset_version or "Session dataset", "left"), P("Analysis version", "small"), P(metadata.analysis_version or "Session analysis", "left")],
    ]
    story.append(table(meta_rows, [31 * mm, 55 * mm, 31 * mm, 55 * mm], header=False, font_size=8))
    story.append(Spacer(1, 5 * mm))

    story.append(P("Analysis design", "h1"))
    story.append(P(analysis_design_summary_text(bundle), "callout"))
    story.append(P(design.classification_tendency_note, "callout"))

    primary = _primary_metric(bundle)
    q = bundle.cochran_q
    summary = [
        [P("Lexical units", "small"), P("Selected raters", "small"), P("Observed agreement", "small"), P(design.primary_agreement_metric, "small")],
        [P(bundle.counts.lexical_units, "center"), P(bundle.counts.raters, "center"), P(_mean_raw_agreement(bundle), "center"), P(_metric_text(primary), "center")],
    ]
    story.append(table(summary, [43 * mm] * 4, header=False, font_size=9))
    story.append(Spacer(1, 5 * mm))

    story.append(P("Raters and analytical scope", "h2"))
    reference_id = bundle.config.reference_rater_id
    rater_rows = [[P("Rater", "small"), P("Role in this analysis", "small")]]
    for rater_id in selected_raters:
        role = "Rater"
        if reference_id == rater_id and bundle.config.analysis_perspective is AnalysisPerspective.REFERENCE_RATER:
            role = "Reference rater"
        elif reference_id == rater_id and bundle.config.analysis_perspective is AnalysisPerspective.EXPERT_BENCHMARK:
            role = "Expert benchmark"
        rater_rows.append([P(names[rater_id], "left"), P(role, "left")])
    story.append(table(rater_rows, [80 * mm, 92 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(P(
        "Sources: " + ", ".join(source_names[sid] for sid in selected_sources) + ". "
        + "Grammatical categories: " + (", ".join(bundle.config.selected_categories) if bundle.config.selected_categories else "All validated categories") + ". "
        + f"Analysis perspective: {_perspective_label(bundle)}.",
        "body",
    ))

    story.append(PageBreak())
    story.append(P("1. Overall agreement", "h1"))
    pair_rows = [[P("Rater pair", "small"), P("N", "small"), P("Observed", "small"), P("Cohen's Kappa", "small"), P("95% CI", "small"), P("Status", "small")]]
    for item in bundle.pairwise:
        pair_rows.append([
            P(f"{names[item.rater_a_id]} x {names[item.rater_b_id]}", "left"),
            P(item.kappa.effective_n, "left"),
            P(_metric_text(item.raw_agreement, percent=True), "left"),
            P(_metric_text(item.kappa), "left"),
            P(_ci_text(item.kappa), "left"),
            P(item.kappa.status.value.replace("_", " ").title(), "left"),
        ])
    story.append(table(pair_rows, [42 * mm, 15 * mm, 25 * mm, 27 * mm, 29 * mm, 34 * mm]))

    if bundle.overall_multirater:
        story.append(P("Global multi-rater agreement", "h2"))
        multi_rows = [[P("Metric", "small"), P("Estimate", "small"), P("Effective N", "small"), P("Status", "small")]]
        metric_labels = {"fleiss_kappa": "Fleiss' Kappa", "krippendorff_alpha": "Krippendorff's alpha"}
        for metric in bundle.overall_multirater:
            multi_rows.append([
                P(metric_labels.get(metric.metric, metric.metric), "left"),
                P(_metric_text(metric), "left"),
                P(metric.effective_n, "left"),
                P(metric.status.value.replace("_", " ").title(), "left"),
            ])
        story.append(table(multi_rows, [55 * mm, 38 * mm, 35 * mm, 44 * mm]))

    story.append(P("Rater classification tendency", "h2"))
    if q is None:
        story.append(P("Cochran's Q was not available for the selected scope."))
    else:
        q_rows = [
            [P("Cochran's Q", "small"), P("df", "small"), P("p-value", "small"), P("Effective N", "small")],
            [P("Not estimable" if q.q is None else f"{q.q:.3f}", "center"), P(q.degrees_of_freedom if q.degrees_of_freedom is not None else "-", "center"), P(_p_text(q.p_value), "center"), P(q.effective_n, "center")],
        ]
        story.append(table(q_rows, [43 * mm] * 4, header=False))
        story.append(P(design.classification_tendency_note, "small"))

    if bundle.expert_benchmark:
        story.append(P("Agreement with expert benchmark", "h2"))
        rows = [[P("Compared rater", "small"), P("Agreement", "small"), P("Sensitivity", "small"), P("Specificity", "small"), P("Precision", "small"), P("Recall", "small")]]
        for item in bundle.expert_benchmark:
            rows.append([
                P(names[item.rater_id], "left"),
                P(_metric_text(item.agreement_with_expert, percent=True), "left"),
                P(_metric_text(item.sensitivity, percent=True), "left"),
                P(_metric_text(item.specificity, percent=True), "left"),
                P(_metric_text(item.precision, percent=True), "left"),
                P(_metric_text(item.recall, percent=True), "left"),
            ])
        story.append(table(rows, [37 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm], font_size=7.3))
        story.append(P("Directional benchmark measures use the selected expert as the comparison benchmark; they do not alter any original annotation.", "small"))

    story.append(PageBreak())
    story.append(P("2. Agreement by grammatical category", "h1"))
    category_chart = _group_chart(bundle.by_category, "Observed agreement by grammatical category")
    if category_chart:
        story.append(_proportional_report_image(category_chart, max_width=172 * mm, max_height=140 * mm))
        story.append(Spacer(1, 2 * mm))
    story.append(P("Protocol statistics by category", "h2"))
    if bundle.counts.raters >= 3:
        category_global_rows = [[
            P("Category", "small"), P("Units", "small"), P("Fleiss' Kappa", "small"),
            P("Cochran's Q", "small"), P("df", "small"), P("p-value", "small"),
        ]]
        for group in bundle.by_category:
            q_group = group.cochran_q
            category_global_rows.append([
                P(group.display_name, "left"),
                P(group.lexical_unit_count, "left"),
                P(_metric_text(group.fleiss_kappa), "left"),
                P("Not estimable" if q_group is None or q_group.q is None else f"{q_group.q:.3f}", "left"),
                P("-" if q_group is None or q_group.degrees_of_freedom is None else q_group.degrees_of_freedom, "left"),
                P("-" if q_group is None else _p_text(q_group.p_value), "left"),
            ])
        story.append(table(category_global_rows, [45 * mm, 18 * mm, 30 * mm, 30 * mm, 18 * mm, 31 * mm], font_size=7.1))
        story.append(P("Fleiss' Kappa is the global agreement coefficient for all selected raters within each grammatical category. Cochran's Q separately tests classification tendency within that category.", "small"))
    else:
        category_global_rows = [[
            P("Category", "small"), P("Units", "small"), P("Cochran's Q", "small"),
            P("df", "small"), P("p-value", "small"),
        ]]
        for group in bundle.by_category:
            q_group = group.cochran_q
            category_global_rows.append([
                P(group.display_name, "left"),
                P(group.lexical_unit_count, "left"),
                P("Not estimable" if q_group is None or q_group.q is None else f"{q_group.q:.3f}", "left"),
                P("-" if q_group is None or q_group.degrees_of_freedom is None else q_group.degrees_of_freedom, "left"),
                P("-" if q_group is None else _p_text(q_group.p_value), "left"),
            ])
        story.append(table(category_global_rows, [58 * mm, 24 * mm, 34 * mm, 20 * mm, 36 * mm], font_size=7.3))
        story.append(P("Cochran's Q is reported within each grammatical category as a classification-tendency test; Cohen's Kappa remains the pairwise agreement coefficient.", "small"))

    story.append(P("Pairwise agreement by category", "h2"))
    category_pair_rows = [[P("Category", "small"), P("Rater pair", "small"), P("Observed", "small"), P("Cohen's Kappa", "small")]]
    for group in bundle.by_category:
        for pair in group.pairwise:
            category_pair_rows.append([
                P(group.display_name, "left"),
                P(f"{names[pair.rater_a_id]} x {names[pair.rater_b_id]}", "left"),
                P(_metric_text(pair.raw_agreement, percent=True), "left"),
                P(_metric_text(pair.kappa), "left"),
            ])
    story.append(table(category_pair_rows, [44 * mm, 62 * mm, 30 * mm, 36 * mm], font_size=7.1))

    if category_association is not None:
        story.append(PageBreak())
        story.append(P("2.1 Grammatical Category Association", "h1"))
        story.append(P(
            "The Fisher-Freeman-Halton exact test evaluates whether metaphor classification is associated "
            "with grammatical category within each rater. This tests association, not inter-rater agreement. "
            "The optional fewer-than-five exclusion rule is a researcher-selected analysis rule, not a "
            "mathematical requirement of the exact test.",
            "callout",
        ))
        if category_association.min_occurrences <= 1:
            inclusion_rule = "Include all selected grammatical categories"
        else:
            inclusion_rule = (
                "Exclude selected grammatical categories with fewer than "
                f"{category_association.min_occurrences} occurrences"
            )
        included = ", ".join(
            f"{category} (n={count})"
            for category, count in category_association.included_categories
        ) or "None"
        excluded = ", ".join(
            f"{category} (n={count})"
            for category, count in category_association.excluded_categories
        ) or "None"
        story.append(P(f"Category inclusion rule: {inclusion_rule}."))
        story.append(P(f"Included categories: {included}.", "small"))
        story.append(P(f"Excluded by the selected rule: {excluded}.", "small"))
        story.append(P(
            f"Per-rater exact p-values are adjusted across the selected raters using "
            f"{category_association.correction} correction.",
            "small",
        ))

        association_rows = [[
            P("Rater", "small"), P("N", "small"), P("Metaphor %", "small"),
            P("Exact p", "small"), P("Adjusted p", "small"), P("Interpretation", "small"),
        ]]
        for result in category_association.raters:
            metaphor_count = sum(row.metaphor_count for row in result.rows)
            observed = sum(row.metaphor_count + row.non_metaphor_count for row in result.rows)
            metaphor_percent = "-" if observed == 0 else f"{100 * metaphor_count / observed:.1f}%"
            if result.adjusted_p_value is None:
                interpretation = "Not estimable"
            elif result.adjusted_p_value < 0.05:
                interpretation = "Evidence of association"
            else:
                interpretation = "No evidence of association"
            association_rows.append([
                P(names.get(result.rater_id, result.rater_id), "left"),
                P(result.effective_n, "left"),
                P(metaphor_percent, "left"),
                P(_exact_p_text(result.p_value), "left"),
                P(_exact_p_text(result.adjusted_p_value), "left"),
                P(interpretation, "left"),
            ])
        story.append(table(association_rows, [34 * mm, 18 * mm, 28 * mm, 25 * mm, 27 * mm, 40 * mm], font_size=6.9))

        detail_rows = [[
            P("Rater", "small"), P("Category", "small"), P("Occurrences", "small"),
            P("M", "small"), P("N", "small"), P("Missing", "small"),
        ]]
        for result in category_association.raters:
            for row in result.rows:
                detail_rows.append([
                    P(names.get(result.rater_id, result.rater_id), "left"),
                    P(row.category, "left"),
                    P(row.occurrence_count, "left"),
                    P(row.metaphor_count, "left"),
                    P(row.non_metaphor_count, "left"),
                    P(row.missing_count, "left"),
                ])
        if len(detail_rows) > 1:
            story.append(P("Per-rater contingency counts", "h2"))
            story.append(table(detail_rows, [38 * mm, 42 * mm, 26 * mm, 20 * mm, 20 * mm, 26 * mm], font_size=6.8))
            story.append(P("Legend: M = metaphor; N = non-metaphor.", "small"))

    story.append(PageBreak())
    story.append(P("3. Agreement by source", "h1"))
    source_chart = _group_chart(bundle.by_source, "Observed agreement by source")
    if source_chart:
        story.append(_proportional_report_image(source_chart, max_width=172 * mm, max_height=140 * mm))
        story.append(Spacer(1, 2 * mm))
    story.append(P("Protocol statistics by source", "h2"))
    if bundle.counts.raters >= 3:
        source_global_rows = [[
            P("Source", "small"), P("Units", "small"), P("Fleiss' Kappa", "small"),
            P("Cochran's Q", "small"), P("df", "small"), P("p-value", "small"),
        ]]
        for group in bundle.by_source:
            q_group = group.cochran_q
            source_global_rows.append([
                P(group.display_name, "left"),
                P(group.lexical_unit_count, "left"),
                P(_metric_text(group.fleiss_kappa), "left"),
                P("Not estimable" if q_group is None or q_group.q is None else f"{q_group.q:.3f}", "left"),
                P("-" if q_group is None or q_group.degrees_of_freedom is None else q_group.degrees_of_freedom, "left"),
                P("-" if q_group is None else _p_text(q_group.p_value), "left"),
            ])
        story.append(table(source_global_rows, [51 * mm, 18 * mm, 29 * mm, 29 * mm, 16 * mm, 29 * mm], font_size=6.9))
        story.append(P("Fleiss' Kappa is the global agreement coefficient for all selected raters within each source table. Cochran's Q separately tests classification tendency within that source.", "small"))
    else:
        source_global_rows = [[
            P("Source", "small"), P("Units", "small"), P("Cochran's Q", "small"),
            P("df", "small"), P("p-value", "small"),
        ]]
        for group in bundle.by_source:
            q_group = group.cochran_q
            source_global_rows.append([
                P(group.display_name, "left"),
                P(group.lexical_unit_count, "left"),
                P("Not estimable" if q_group is None or q_group.q is None else f"{q_group.q:.3f}", "left"),
                P("-" if q_group is None or q_group.degrees_of_freedom is None else q_group.degrees_of_freedom, "left"),
                P("-" if q_group is None else _p_text(q_group.p_value), "left"),
            ])
        story.append(table(source_global_rows, [66 * mm, 22 * mm, 32 * mm, 18 * mm, 34 * mm], font_size=7.1))
        story.append(P("Cochran's Q is reported within each source table as a classification-tendency test; Cohen's Kappa remains the pairwise agreement coefficient.", "small"))

    story.append(P("Pairwise agreement by source", "h2"))
    source_pair_rows = [[P("Source", "small"), P("Rater pair", "small"), P("Observed", "small"), P("Cohen's Kappa", "small")]]
    for group in bundle.by_source:
        for pair in group.pairwise:
            source_pair_rows.append([
                P(group.display_name, "left"),
                P(f"{names[pair.rater_a_id]} x {names[pair.rater_b_id]}", "left"),
                P(_metric_text(pair.raw_agreement, percent=True), "left"),
                P(_metric_text(pair.kappa), "left"),
            ])
    story.append(table(source_pair_rows, [54 * mm, 58 * mm, 28 * mm, 32 * mm], font_size=7.0))

    story.append(PageBreak())
    story.append(P("4. Disagreement review", "h1"))
    unit_ids = _selected_unit_ids(dataset, bundle)
    cases = build_review_cases(dataset, selected_raters=selected_raters, unit_ids=unit_ids)
    disagreements = [case for case in cases if case.status is ReviewStatus.DISAGREEMENT]
    story.append(P(f"{len(disagreements)} disagreement cases were found in the current analytical scope. These cases identify where raters differ; they do not imply that any rater is incorrect."))
    disagreement_chart = _disagreement_chart(dataset, bundle)
    if disagreement_chart:
        story.append(_proportional_report_image(disagreement_chart, max_width=172 * mm, max_height=90 * mm))
        story.append(Spacer(1, 2 * mm))
    if disagreements:
        rows = [[P("Source", "small"), P("Lexical unit", "small"), P("POS", "small"), P("Rater classifications", "small")]]
        for case in disagreements:
            classifications = []
            for rater_id, value in case.rater_classifications:
                symbol = {Classification.METAPHOR: "M", Classification.NON_METAPHOR: "N", Classification.MISSING: "-"}[value]
                classifications.append(f"{names.get(rater_id, rater_id)}={symbol}")
            rows.append([
                P(case.source_display_name, "left"), P(case.lexical_unit, "left"),
                P(case.grammatical_category, "left"), P("; ".join(classifications), "left"),
            ])
        story.append(table(rows, [43 * mm, 35 * mm, 28 * mm, 66 * mm], font_size=7.0))
        story.append(P("Legend: M = metaphor, N = non-metaphor, - = missing rating.", "small"))
    else:
        story.append(P("No disagreement cases were present for the selected scope."))

    story.append(Spacer(1, 5 * mm))
    story.append(P("5. Reproducibility and provenance", "h1"))
    reproducibility = [
        ("Software version", metadata.software_version),
        ("Dataset identifier", dataset.dataset_id),
        ("Dataset content SHA-256", dataset_content_hash(dataset)),
        ("Analysis configuration SHA-256", analysis_config_hash(bundle.config)),
        ("Dataset version", metadata.dataset_version or "Session dataset"),
        ("Analysis version", metadata.analysis_version or "Session analysis"),
        ("Analysis perspective", _perspective_label(bundle)),
        ("Reference / benchmark rater", names.get(bundle.config.reference_rater_id or "", "None")),
        ("Multiple-testing correction", bundle.config.multiple_testing_correction),
        (
            "Grammatical-category association rule",
            "Include all selected grammatical categories"
            if bundle.config.category_association_min_occurrences <= 1
            else (
                "Exclude categories with fewer than "
                f"{bundle.config.category_association_min_occurrences} occurrences"
            ),
        ),
        ("Random seed", bundle.config.random_seed),
        ("Bootstrap samples", bundle.config.bootstrap_samples),
        ("Generated at", generated_at),
    ]
    rep_rows = [[P("Field", "small"), P("Value", "small")]] + [[P(k, "left"), P(v, "left")] for k, v in reproducibility]
    story.append(table(rep_rows, [55 * mm, 117 * mm], font_size=7.3))
    story.append(Spacer(1, 4 * mm))
    story.append(P(
        "Methodological note: agreement coefficients and classification-tendency tests answer different questions. "
        "Cohen's Kappa is pairwise; Fleiss' Kappa is the primary global agreement coefficient when three or more "
        "raters are selected; Cochran's Q examines marginal classification tendency. The Fisher-Freeman-Halton "
        "exact test evaluates grammatical-category association within each rater and is not an agreement coefficient. "
        "Krippendorff's alpha is included as an advanced complementary multi-rater estimate when available.",
        "callout",
    ))
    story.append(P("This report is generated from the validated analytical dataset. The original source workbook is not modified.", "small"))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
