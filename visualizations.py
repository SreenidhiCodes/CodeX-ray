"""
visualizations.py
==================
Chart-building helpers for CodeXray's dashboard. Every function here
returns a Plotly Figure — it never calls `st.*` directly — so these are
easy to unit-test and reusable outside Streamlit if needed.

dashboard.py is responsible for laying figures out on the page
(st.plotly_chart(...)); this module is only responsible for building them.

Public API
----------
ai_gauge_chart(score_pct, title="AI-Generation Indicator") -> go.Figure
overall_similarity_donut(score_pct, title="Overall Similarity") -> go.Figure
similarity_breakdown_bar(components, title="Similarity Breakdown") -> go.Figure
dual_ai_indicator_bar(code1_pct, code2_pct, labels=("Code 1","Code 2")) -> go.Figure
batch_similarity_bar(pairs, top_n=15, threshold=80) -> go.Figure
"""

from __future__ import annotations

import plotly.graph_objects as go

# Color thresholds shared across charts, so "high similarity" always reads
# the same color no matter which chart it's in.
_LOW_COLOR = "#2ecc71"      # green  - low similarity / low AI likelihood
_MED_COLOR = "#f1c40f"      # yellow - moderate
_HIGH_COLOR = "#e74c3c"     # red    - high similarity / high AI likelihood


def _band_color(pct: float) -> str:
    if pct >= 75:
        return _HIGH_COLOR
    if pct >= 45:
        return _MED_COLOR
    return _LOW_COLOR


def _as_pct(value: float) -> float:
    """Accept either a 0-1 fraction or an already-0-100 percentage."""
    return round(value * 100, 1) if 0 <= value <= 1 else round(value, 1)


def ai_gauge_chart(score_pct: float, title: str = "AI-Generation Indicator") -> go.Figure:
    """
    Gauge chart for a single AI-generation-likelihood score.
    score_pct: 0-100 (or 0-1, auto-detected).
    """
    pct = _as_pct(score_pct)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%"},
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": _band_color(pct)},
                "steps": [
                    {"range": [0, 45], "color": "#eafaf1"},
                    {"range": [45, 75], "color": "#fef9e7"},
                    {"range": [75, 100], "color": "#fdedec"},
                ],
            },
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    return fig


def overall_similarity_donut(score_pct: float, title: str = "Overall Similarity") -> go.Figure:
    pct = _as_pct(score_pct)
    fig = go.Figure(
        go.Pie(
            values=[pct, 100 - pct],
            hole=0.72,
            marker=dict(colors=[_band_color(pct), "#ecf0f1"]),
            textinfo="none",
            sort=False,
            direction="clockwise",
        )
    )
    fig.update_layout(
        title=title,
        showlegend=False,
        height=260,
        margin=dict(l=10, r=10, t=50, b=10),
        annotations=[dict(text=f"{pct:g}%", x=0.5, y=0.5, font_size=28, showarrow=False)],
    )
    return fig


def similarity_breakdown_bar(components: dict[str, float], title: str = "Similarity Breakdown") -> go.Figure:
    """
    Horizontal bar chart for the component scores that feed the hybrid
    similarity (Text / AST / Semantic / Fingerprint / Control-Flow / ...).
    `components` values may be 0-1 or 0-100; None values are skipped
    (e.g. semantic_similarity when CodeBERT isn't available).
    """
    labels, values, colors = [], [], []
    for name, val in components.items():
        if val is None:
            continue
        pct = _as_pct(val)
        labels.append(name)
        values.append(pct)
        colors.append(_band_color(pct))

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:g}%" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis=dict(range=[0, 100], title="%"),
        height=90 + 45 * max(len(labels), 1),
        margin=dict(l=10, r=30, t=50, b=30),
    )
    return fig


def dual_ai_indicator_bar(
    code1_pct: float,
    code2_pct: float,
    labels: tuple[str, str] = ("Code 1", "Code 2"),
    title: str = "AI-Generation Indicator — Code 1 vs Code 2",
) -> go.Figure:
    p1, p2 = _as_pct(code1_pct), _as_pct(code2_pct)
    fig = go.Figure(
        go.Bar(
            x=list(labels),
            y=[p1, p2],
            marker_color=[_band_color(p1), _band_color(p2)],
            text=[f"{p1:g}%", f"{p2:g}%"],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        yaxis=dict(range=[0, 100], title="%"),
        height=300,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def batch_similarity_bar(
    pairs: list[dict],
    top_n: int = 15,
    threshold: float = 80,
    title: str = "Top Similar Pairs",
) -> go.Figure:
    """
    pairs: list of {"pair": "student1 <-> student7", "similarity": 91.0}
    (or "label"/"score" — both key names are accepted).
    Bars at/above `threshold` are colored red as a flagged-pair cue.
    """
    normed = []
    for p in pairs:
        label = p.get("pair") or p.get("label") or f"{p.get('a', '?')} <-> {p.get('b', '?')}"
        score = p.get("similarity", p.get("score", 0))
        normed.append((label, _as_pct(score)))
    normed.sort(key=lambda t: t[1], reverse=True)
    normed = normed[:top_n]

    labels = [n[0] for n in reversed(normed)]
    values = [n[1] for n in reversed(normed)]
    colors = [_HIGH_COLOR if v >= threshold else _band_color(v) for v in values]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:g}%" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis=dict(range=[0, 100], title="%"),
        height=60 + 32 * max(len(labels), 1),
        margin=dict(l=10, r=30, t=50, b=30),
    )
    return fig


if __name__ == "__main__":
    # Smoke test — builds each figure, doesn't render (no Streamlit needed).
    figs = [
        ai_gauge_chart(78),
        overall_similarity_donut(87),
        similarity_breakdown_bar({"Text": 72, "AST": 94, "Semantic": 89}),
        dual_ai_indicator_bar(82, 51),
        batch_similarity_bar(
            [
                {"pair": "student1 <-> student7", "similarity": 91},
                {"pair": "student2 <-> student5", "similarity": 84},
                {"pair": "student3 <-> student9", "similarity": 43},
            ]
        ),
    ]
    print(f"Built {len(figs)} figures OK")
