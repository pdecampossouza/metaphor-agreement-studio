from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from metaphor_agreement_studio.statistics.types import AnalysisConfig, EstimateStatus, PairwiseResult

REPORTING_WARNING = (
    "Automatically generated statistical description. Review substantive interpretation before using it in a thesis or manuscript."
)
_TEMPLATE_DIR = Path(__file__).with_name("templates")
_ENV = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), undefined=StrictUndefined, autoescape=False)


def _number_word(value: int) -> str:
    return {1: "one rater", 2: "two raters", 3: "three raters", 4: "four raters", 5: "five raters"}.get(value, f"{value} raters")


def suggest_statistical_reporting(result_context: PairwiseResult) -> str:
    raw = result_context.raw_agreement.value
    kappa = result_context.kappa
    if kappa.value is None and kappa.status is EstimateStatus.NOT_ESTIMABLE_NO_VARIATION:
        sentence = (
            f"Observed agreement was complete ({raw * 100:.1f}%; N = {kappa.effective_n}), but Cohen's Kappa was not estimable because there was an absence of variation in the classifications."
            if raw is not None
            else "Cohen's Kappa was not estimable because there was an absence of variation in the classifications."
        )
    elif kappa.value is None:
        sentence = f"Cohen's Kappa was not estimable for this comparison (N = {kappa.effective_n})."
    else:
        raw_text = "not available" if raw is None else f"{raw * 100:.1f}%"
        ci = ""
        if kappa.ci_low is not None and kappa.ci_high is not None:
            ci = f", 95% CI [{kappa.ci_low:.2f}, {kappa.ci_high:.2f}]"
        sentence = (
            f"Observed agreement between the selected raters was {raw_text}; chance-corrected agreement was Cohen's κ = {kappa.value:.2f}{ci} (N = {kappa.effective_n})."
        )
    return f"{sentence}\n\n{REPORTING_WARNING}"


def generate_method_summary(config: AnalysisConfig, rater_count: int) -> str:
    template = _ENV.get_template("method_summary.txt.j2")
    return template.render(
        rater_count_text=_number_word(rater_count),
        multirater=rater_count >= 3,
        pairwise=rater_count >= 2,
        correction=config.multiple_testing_correction.replace("-", " ").title(),
    ).strip()
