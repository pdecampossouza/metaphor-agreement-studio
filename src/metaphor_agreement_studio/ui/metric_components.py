from __future__ import annotations

from dataclasses import dataclass

from metaphor_agreement_studio.statistics.types import EstimateStatus, MetricResult


@dataclass(frozen=True, slots=True)
class MetricDisplayModel:
    label: str
    value: str
    effective_n: int
    status: str
    explanation: str
    confidence_interval: str | None = None


_STATUS_COPY = {
    EstimateStatus.OK: ("Estimated", "The statistic was estimated from the available validated annotations."),
    EstimateStatus.DESCRIPTIVE_ONLY: (
        "Descriptive only",
        "This subset is too small or lacks the conditions needed for an informative inferential estimate.",
    ),
    EstimateStatus.NOT_ESTIMABLE_NO_VARIATION: (
        "Not estimable",
        "Observed classifications show no variation, so a chance-corrected coefficient cannot be estimated.",
    ),
    EstimateStatus.INSUFFICIENT_PAIRED_OBSERVATIONS: (
        "Not estimable",
        "There are not enough paired observations for this statistic.",
    ),
    EstimateStatus.INCOMPLETE_FOR_METRIC: (
        "Incomplete",
        "The available annotation pattern does not satisfy the requirements of this metric.",
    ),
}


def metric_display_model(
    label: str,
    result: MetricResult,
    *,
    percent: bool = False,
) -> MetricDisplayModel:
    status, explanation = _STATUS_COPY[result.status]
    if result.value is None:
        value = status
    elif percent:
        value = f"{result.value * 100:.1f}%"
    else:
        value = f"{result.value:.3f}"
    ci = None
    if result.ci_low is not None and result.ci_high is not None:
        ci = f"95% CI [{result.ci_low:.3f}, {result.ci_high:.3f}]"
    return MetricDisplayModel(
        label=label,
        value=value,
        effective_n=result.effective_n,
        status=status,
        explanation=explanation,
        confidence_interval=ci,
    )


def render_metric_result(
    label: str,
    result: MetricResult,
    explanation_key: str | None = None,
    *,
    percent: bool = False,
) -> None:
    import streamlit as st

    from metaphor_agreement_studio.statistics.explanations import explanation_text

    model = metric_display_model(label, result, percent=percent)
    st.metric(model.label, model.value)
    details = [f"Effective N: {model.effective_n}", model.status]
    if model.confidence_interval:
        details.append(model.confidence_interval)
    st.caption(" · ".join(details))
    if result.status is not EstimateStatus.OK:
        st.caption(model.explanation)
    if explanation_key:
        with st.expander("Technical details", icon=":material/functions:"):
            st.markdown(explanation_text(explanation_key))
