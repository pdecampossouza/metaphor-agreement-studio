from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from metaphor_agreement_studio.figures.types import FigureDataset, FigureKind, FigureSpec, SEMANTIC_MARKERS


def _clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def _pairwise_heatmap(spec: FigureSpec, data: FigureDataset) -> go.Figure:
    frame = data.frame
    raters = list(dict.fromkeys(frame["rater_a"].tolist() + frame["rater_b"].tolist()))
    lookup = {(row.rater_a, row.rater_b): row for row in frame.itertuples(index=False)}
    z = []
    text = []
    custom = []
    for a in raters:
        z_row, text_row, custom_row = [], [], []
        for b in raters:
            row = lookup.get((a, b))
            estimate = _clean(row.estimate) if row else None
            z_row.append(estimate)
            text_row.append("—" if a == b or estimate is None else f"{estimate:.2f}")
            if row is None or a == b:
                custom_row.append([a, b, None, None, None, None, None])
            else:
                custom_row.append(
                    [a, b, row.estimate, row.raw_agreement, row.n, row.ci_low, row.ci_high]
                )
        z.append(z_row)
        text.append(text_row)
        custom.append(custom_row)
    heatmap = go.Heatmap(
        z=z,
        x=raters,
        y=raters,
        text=text,
        texttemplate="%{text}",
        customdata=custom,
        zmin=-1,
        zmax=1,
        colorscale="RdBu",
        reversescale=True,
        hovertemplate=(
            "%{customdata[0]} × %{customdata[1]}<br>"
            "Cohen's κ: %{customdata[2]:.3f}<br>"
            "Raw agreement: %{customdata[3]:.1%}<br>"
            "Effective N: %{customdata[4]:.0f}<br>"
            "95% CI: [%{customdata[5]:.3f}, %{customdata[6]:.3f}]<extra></extra>"
        ),
        colorbar={"title": "Cohen's κ"},
    )
    fig = go.Figure(heatmap)
    fig.update_layout(title=spec.title, xaxis_title="Rater", yaxis_title="Rater")
    return fig


def _point_interval(spec: FigureSpec, data: FigureDataset, label_column: str) -> go.Figure:
    frame = data.frame.copy()
    frame = frame.sort_values("estimate", na_position="first")
    valid = frame[frame["estimate"].notna()]
    invalid = frame[frame["estimate"].isna()]
    err_plus = []
    err_minus = []
    for row in valid.itertuples(index=False):
        hi = _clean(row.ci_high)
        lo = _clean(row.ci_low)
        err_plus.append(max(0.0, hi - row.estimate) if hi is not None else 0.0)
        err_minus.append(max(0.0, row.estimate - lo) if lo is not None else 0.0)
    fig = go.Figure()
    if not valid.empty:
        fig.add_trace(
            go.Scatter(
                x=valid["estimate"],
                y=valid[label_column],
                mode="markers",
                marker={"symbol": "circle", "size": 10},
                error_x={"type": "data", "array": err_plus, "arrayminus": err_minus, "visible": True},
                customdata=valid[["n", "raw_agreement", "status"]],
                hovertemplate=(
                    "%{y}<br>Cohen's κ: %{x:.3f}<br>Effective N: %{customdata[0]}<br>"
                    "Raw agreement: %{customdata[1]:.1%}<br>Status: %{customdata[2]}<extra></extra>"
                ),
                name="Estimated",
            )
        )
    if not invalid.empty:
        fig.add_trace(
            go.Scatter(
                x=[0] * len(invalid),
                y=invalid[label_column],
                mode="markers+text",
                marker={"symbol": "circle-open", "size": 10},
                text=["descriptive only"] * len(invalid),
                textposition="middle right",
                customdata=invalid[["n", "status"]],
                hovertemplate="%{y}<br>Effective N: %{customdata[0]}<br>Status: %{customdata[1]}<extra></extra>",
                name="Not estimable",
            )
        )
    fig.update_layout(title=spec.title, xaxis_title="Cohen's κ", yaxis_title="")
    fig.update_xaxes(range=[-1, 1])
    return fig


def _fingerprint(spec: FigureSpec, data: FigureDataset) -> go.Figure:
    frame = data.frame.copy()
    if frame.empty:
        return go.Figure(layout={"title": spec.title})
    labels = (
        frame[["unit_id", "lexical_unit", "source", "category", "occurrence_index"]]
        .drop_duplicates("unit_id")
        .assign(label=lambda d: d["lexical_unit"].astype(str) + " · " + d["source"].astype(str))
    )
    order = labels["unit_id"].tolist()
    label_lookup = dict(zip(labels["unit_id"], labels["label"], strict=True))
    fig = go.Figure()
    for classification in ("Metaphor", "Non-metaphor", "Missing"):
        subset = frame[frame["classification"] == classification]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["rater"],
                y=[label_lookup[u] for u in subset["unit_id"]],
                mode="markers",
                marker={"symbol": SEMANTIC_MARKERS[classification], "size": 10},
                customdata=subset[["source", "category", "lexical_unit", "rater", "requires_review"]],
                hovertemplate=(
                    "Source: %{customdata[0]}<br>POS: %{customdata[1]}<br>Lexical unit: %{customdata[2]}<br>"
                    "Rater: %{customdata[3]}<br>Classification: "
                    + classification
                    + "<br>Inter-rater disagreement: %{customdata[4]}<extra></extra>"
                ),
                name=classification,
            )
        )
    fig.update_layout(title=spec.title, xaxis_title="Rater", yaxis_title="Lexical occurrence")
    fig.update_yaxes(categoryorder="array", categoryarray=[label_lookup[u] for u in reversed(order)])
    return fig


def _bar(spec: FigureSpec, data: FigureDataset, x: str, y: str, y_title: str, suffix: str = "") -> go.Figure:
    frame = data.frame
    fig = go.Figure(
        go.Bar(
            x=frame[x],
            y=frame[y],
            text=[f"{v:.1%}" if suffix == "%" and pd.notna(v) else str(v) for v in frame[y]],
            textposition="outside",
        )
    )
    fig.update_layout(title=spec.title, xaxis_title="", yaxis_title=y_title)
    return fig


def render_interactive_figure(spec: FigureSpec, data: FigureDataset) -> go.Figure:
    kind = spec.kind
    if kind is FigureKind.PAIRWISE_KAPPA_MATRIX:
        return _pairwise_heatmap(spec, data)
    if kind is FigureKind.AGREEMENT_FINGERPRINT:
        return _fingerprint(spec, data)
    if kind is FigureKind.AGREEMENT_BY_CATEGORY:
        return _point_interval(spec, data, "category")
    if kind is FigureKind.SOURCE_COMPARISON:
        return _point_interval(spec, data, "source")
    if kind is FigureKind.AGREEMENT_VS_SAMPLE_SIZE:
        frame = data.frame
        fig = go.Figure(
            go.Scatter(
                x=frame["n"],
                y=frame["raw_agreement"],
                mode="markers+text",
                text=frame["category"],
                textposition="top center",
                customdata=frame[["estimate", "status"]],
                hovertemplate=(
                    "%{text}<br>N: %{x}<br>Raw agreement: %{y:.1%}<br>"
                    "Cohen's κ: %{customdata[0]:.3f}<br>Status: %{customdata[1]}<extra></extra>"
                ),
            )
        )
        fig.update_layout(title=spec.title, xaxis_title="Lexical units (N)", yaxis_title="Raw agreement")
        return fig
    if kind is FigureKind.METAPHOR_RATE_BY_RATER:
        return _bar(spec, data, "rater", "rate", "Metaphor classification rate", "%")
    if kind is FigureKind.DISAGREEMENT_BY_CATEGORY:
        return _bar(spec, data, "category", "rate", "Disagreement rate", "%")
    if kind is FigureKind.RATER_DIVERGENCE:
        frame = data.frame.sort_values("mean_pairwise_kappa")
        fig = go.Figure(
            go.Scatter(
                x=frame["mean_pairwise_kappa"],
                y=frame["rater"],
                mode="markers",
                customdata=frame[["comparisons"]],
                hovertemplate="%{y}<br>Mean pairwise κ: %{x:.3f}<br>Comparisons: %{customdata[0]}<extra></extra>",
            )
        )
        fig.update_layout(title=spec.title, xaxis_title="Mean pairwise Cohen's κ", yaxis_title="")
        return fig
    if kind is FigureKind.MULTI_RATER_PATTERNS:
        from plotly.subplots import make_subplots

        frame = data.frame.reset_index(drop=True)
        raters = tuple(data.metadata.get("raters", ()))
        if not raters:
            raters = tuple(sorted({r for values in frame.get("raters", ()) for r in values}))
        positions = list(range(len(frame)))
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.62, 0.38],
            vertical_spacing=0.08,
        )
        fig.add_trace(
            go.Bar(
                x=positions,
                y=frame["count"],
                customdata=frame[["pattern"]],
                hovertemplate="Pattern: %{customdata[0]}<br>Lexical units: %{y}<extra></extra>",
                name="Count",
            ),
            row=1,
            col=1,
        )
        rater_pos = {rater: idx for idx, rater in enumerate(raters)}
        for pattern_index, row in frame.iterrows():
            selected = tuple(row["raters"])
            selected_positions = [rater_pos[r] for r in selected if r in rater_pos]
            if len(selected_positions) >= 2:
                fig.add_trace(
                    go.Scatter(
                        x=[pattern_index, pattern_index],
                        y=[min(selected_positions), max(selected_positions)],
                        mode="lines",
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=2,
                    col=1,
                )
        for rater in raters:
            y_value = rater_pos[rater]
            symbols = ["circle" if rater in tuple(values) else "circle-open" for values in frame["raters"]]
            fig.add_trace(
                go.Scatter(
                    x=positions,
                    y=[y_value] * len(frame),
                    mode="markers",
                    marker={"symbol": symbols, "size": 9},
                    customdata=frame[["pattern"]],
                    hovertemplate=(
                        f"Rater: {rater}<br>Pattern: %{{customdata[0]}}<br>"
                        "Filled marker = classified as metaphor<extra></extra>"
                    ),
                    name=rater,
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
        fig.update_yaxes(title_text="Lexical units", row=1, col=1)
        fig.update_yaxes(
            tickmode="array",
            tickvals=list(range(len(raters))),
            ticktext=list(raters),
            autorange="reversed",
            row=2,
            col=1,
        )
        fig.update_xaxes(
            tickmode="array",
            tickvals=positions,
            ticktext=frame["pattern"].tolist(),
            tickangle=-30,
            row=2,
            col=1,
        )
        fig.update_layout(title=spec.title, showlegend=False)
        return fig
    if kind is FigureKind.SPECIFIC_AGREEMENT:
        frame = data.frame
        fig = go.Figure()
        for classification, subset in frame.groupby("classification", sort=False):
            fig.add_trace(
                go.Bar(
                    x=[f"{a} × {b}" for a, b in zip(subset["rater_a"], subset["rater_b"], strict=True)],
                    y=subset["estimate"],
                    name=classification,
                    marker={"pattern": {"shape": "/" if classification == "Metaphor" else "x"}},
                    hovertemplate="%{x}<br>" + classification + " agreement: %{y:.1%}<extra></extra>",
                )
            )
        fig.update_layout(title=spec.title, barmode="group", yaxis_title="Specific agreement")
        return fig
    if kind is FigureKind.REVIEW_DENSITY:
        frame = data.frame
        sizes = [8 + 30 * value for value in frame["rate"]] if not frame.empty else []
        fig = go.Figure(
            go.Scatter(
                x=frame["category"],
                y=frame["source"],
                mode="markers",
                marker={"size": sizes, "symbol": "diamond"},
                customdata=frame[["disagreement_cases", "n", "rate"]],
                hovertemplate=(
                    "%{y} · %{x}<br>Disagreement cases: %{customdata[0]} / %{customdata[1]}"
                    "<br>Rate: %{customdata[2]:.1%}<extra></extra>"
                ),
            )
        )
        fig.update_layout(title=spec.title, xaxis_title="Grammatical category", yaxis_title="Source")
        return fig
    raise ValueError(f"Unsupported interactive figure kind: {kind}")
