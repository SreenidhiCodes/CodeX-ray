"""
dashboard.py
=============
CodeXray's result screens. This module takes the structured result
dicts produced by the backend (ultimately Member 3's
report_generator.py) and renders them as the three screens CodeXray
needs:

    render_single_code_dashboard(result)   -> "Analyze One Code"
    render_comparison_dashboard(result)    -> "Compare Two Codes"
    render_batch_dashboard(pairs)          -> "Batch Analysis"

Expected input shapes
----------------------
Single-code `result`:
    {
        "ai_indicator": 78,                 # 0-100 or 0-1
        "ai_confidence": "medium",          # optional
        "indicators": ["Highly regular structure", ...],   # optional
        "statistics": {
            "loc": 32, "functions": 4, "loops": 3,
            "conditions": 5, "classes": 0, "complexity": 7,
            "variables": 6, "imports": 1,      # optional extras
        },
        "code": "...",                      # optional, shown in an expander
    }

Comparison `result` (matches Member 3's report_generator.py schema):
    {
        "overall_similarity": 87,           # 0-100 or 0-1
        "text_similarity": 72, "ast_similarity": 94, "semantic_similarity": 89,
        "ai_indicator_code1": 82, "ai_indicator_code2": 51,
        "same_objective": "Likely", "same_approach": False,
        "detected_patterns": ["Similar function structure", ...],
        "code1_statistics": {...}, "code2_statistics": {...},
        "code1": "...", "code2": "...",
        "approach": {"code1_approach": "Iterative", "code2_approach": "Built-in function"},
    }

Batch `pairs`: list of {"pair": "student1 <-> student7", "similarity": 91}

This module is deliberately tolerant of missing keys (teammates'
modules are still being built) — anything absent is just skipped
rather than raising, so the dashboard is demo-able today and fills in
as report_generator.py grows.
"""

from __future__ import annotations

import streamlit as st

import code_viewer
import visualizations as viz

FLAG_THRESHOLD = 80  # overall similarity % at/above which we call out possible plagiarism


def _get(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _pct(value) -> float:
    if value is None:
        return 0.0
    return round(value * 100, 1) if 0 <= value <= 1 else round(value, 1)


# --------------------------------------------------------------------------
# Screen 1 — Analyze One Code
# --------------------------------------------------------------------------
def render_single_code_dashboard(result: dict) -> None:
    st.subheader("Analysis Result")

    col_gauge, col_stats = st.columns([1, 1.3])

    with col_gauge:
        ai_pct = _pct(_get(result, "ai_indicator", "ai_generation_likelihood", default=0))
        st.plotly_chart(viz.ai_gauge_chart(ai_pct), width="stretch")
        conf = result.get("ai_confidence")
        if conf:
            st.caption(f"Confidence: {conf}")
        analysis = result.get("ai_analysis", {})
        if result.get("ai_method"):
            st.caption(f"Scoring method: {result['ai_method']}")
        if analysis.get("parseable") is False:
            st.warning("This style estimate is based on the available source text because the snippet is incomplete or has invalid syntax.")
        st.caption(analysis.get("disclaimer", "Style indicators are not calibrated proof of AI authorship."))

    with col_stats:
        st.markdown("**Code Statistics**")
        stats = result.get("statistics", {})
        stat_fields = [
            ("LOC", _get(stats, "loc", "lines_of_code")),
            ("Functions", stats.get("functions")),
            ("Loops", stats.get("loops")),
            ("Conditions", stats.get("conditions")),
            ("Classes", stats.get("classes")),
            ("Complexity", _get(stats, "complexity", "cyclomatic_complexity")),
        ]
        stat_fields = [(name, v) for name, v in stat_fields if v is not None]
        if stat_fields:
            cols = st.columns(3)
            for i, (name, value) in enumerate(stat_fields):
                cols[i % 3].metric(name, value)
        else:
            st.caption("No statistics available yet.")

        extra = [(k.replace("_", " ").title(), v) for k, v in stats.items()
                 if k not in {"loc", "lines_of_code", "functions", "loops", "conditions",
                              "classes", "complexity", "cyclomatic_complexity"}]
        if extra:
            with st.expander("More statistics"):
                for name, value in extra:
                    st.write(f"{name}: {value}")

    indicators = result.get("indicators") or []
    if indicators:
        st.markdown("**AI-Code Indicators**")
        for line in indicators:
            st.markdown(f"- \u2713 {line}")

    code = result.get("code")
    if code:
        with st.expander("View code"):
            st.code(code, language="python")


# --------------------------------------------------------------------------
# Screen 2 — Compare Two Codes
# --------------------------------------------------------------------------
def render_comparison_dashboard(result: dict) -> None:
    st.subheader("Code Comparison")

    if result.get("comparison_notice"):
        st.warning(result["comparison_notice"])
    elif result.get("semantic_available") is False:
        if result.get("semantic_requested"):
            st.warning("CodeBERT could not be loaded; the overall score uses the available local comparison signals.")
        else:
            st.caption("CodeBERT is opt-in. The overall score uses the available local comparison signals.")

    overall = _pct(_get(result, "overall_similarity", "overall_similarity_pct", default=0))

    col_donut, col_bars = st.columns([1, 1.4])
    with col_donut:
        st.plotly_chart(viz.overall_similarity_donut(overall), width="stretch")
        if overall >= FLAG_THRESHOLD:
            st.error(f"High similarity ({overall:g}%) — worth a closer look.")
    with col_bars:
        components = {
            "Text": result.get("text_similarity"),
            "AST / Logic": _get(result, "ast_similarity", "ast_logic_similarity"),
            "Semantic": result.get("semantic_similarity"),
            "Fingerprint": result.get("fingerprint_similarity"),
            "Control Flow": result.get("control_flow_similarity"),
            "Syntax token pattern": result.get("syntax_token_similarity"),
        }
        components = {k: v for k, v in components.items() if v is not None}
        if components:
            st.plotly_chart(viz.similarity_breakdown_bar(components), width="stretch")

    ai1 = result.get("ai_indicator_code1")
    ai2 = result.get("ai_indicator_code2")
    if ai1 is not None and ai2 is not None:
        st.plotly_chart(
            viz.dual_ai_indicator_bar(_pct(ai1), _pct(ai2)),
            width="stretch",
        )

    patterns = result.get("detected_patterns") or []
    if patterns:
        st.markdown("**Why was similarity detected?**")
        for p in patterns:
            st.markdown(f"- \u2713 {p}")

    _render_approach_panel(result)

    code1, code2 = result.get("code1"), result.get("code2")
    if code1 and code2:
        st.markdown("---")
        st.markdown("**Side-by-Side Code Viewer**")
        code_viewer.render_side_by_side(code1, code2, semantic_notes=result.get("semantic_notes"))


def _render_approach_panel(result: dict) -> None:
    same_objective = result.get("same_objective")
    same_approach = result.get("same_approach")
    approach = result.get("approach", {})
    if same_objective is None and same_approach is None and not approach:
        return

    st.markdown("---")
    st.markdown("**Approach Analysis**")
    c1, c2 = st.columns(2)
    if same_objective is not None:
        c1.metric("Same objective", str(same_objective))
    if same_approach is not None:
        c2.metric("Same implementation approach", "Yes" if same_approach else "No")

    a1 = approach.get("code1_approach")
    a2 = approach.get("code2_approach")
    if a1 or a2:
        st.write(f"Code 1 \u2192 {a1 or 'Unknown'}")
        st.write(f"Code 2 \u2192 {a2 or 'Unknown'}")

    if same_approach is False:
        st.info("Different implementation approaches detected.")
    for note in approach.get("notes", []):
        st.caption(note)


# --------------------------------------------------------------------------
# Screen 3 — Batch Analysis
# --------------------------------------------------------------------------
def render_batch_dashboard(pairs: list[dict]) -> None:
    st.subheader("Batch Analysis")
    if not pairs:
        st.info("No pairs to show yet — upload a batch of files to compare.")
        return

    normed = []
    for p in pairs:
        label = p.get("pair") or p.get("label") or f"{p.get('a', '?')} \u2194 {p.get('b', '?')}"
        score = _pct(p.get("similarity", p.get("score", 0)))
        normed.append({"Code Pair": label, "Similarity": score})
    normed.sort(key=lambda r: r["Similarity"], reverse=True)

    flagged = sum(1 for r in normed if r["Similarity"] >= FLAG_THRESHOLD)
    c1, c2, c3 = st.columns(3)
    c1.metric("Pairs compared", len(normed))
    c2.metric(f"Flagged (\u2265{FLAG_THRESHOLD}%)", flagged)
    c3.metric("Highest similarity", f"{normed[0]['Similarity']:g}%")

    st.plotly_chart(viz.batch_similarity_bar(pairs, threshold=FLAG_THRESHOLD), width="stretch")

    st.dataframe(
        normed,
        width="stretch",
        column_config={
            "Similarity": st.column_config.ProgressColumn(
                "Similarity", format="%.0f%%", min_value=0, max_value=100
            )
        },
        hide_index=True,
    )


# --------------------------------------------------------------------------
# Standalone demo (streamlit run dashboard.py) — uses mock data only,
# so this file can be sanity-checked before report_generator.py exists.
# --------------------------------------------------------------------------
if __name__ == "__main__":
    st.set_page_config(page_title="CodeXray — Dashboard Preview", layout="wide")
    st.title("CODEXRAY — Dashboard Preview (mock data)")

    tab1, tab2, tab3 = st.tabs(["Single Code", "Comparison", "Batch"])

    with tab1:
        render_single_code_dashboard(
            {
                "ai_indicator": 78,
                "ai_confidence": "medium",
                "indicators": [
                    "Highly regular structure",
                    "Repetitive naming pattern",
                    "Consistent formatting",
                ],
                "statistics": {"loc": 32, "functions": 4, "loops": 3, "conditions": 5,
                                "classes": 0, "complexity": 7},
                "code": "def maximum(arr):\n    m = arr[0]\n    for x in arr:\n        if x > m:\n            m = x\n    return m",
            }
        )

    with tab2:
        render_comparison_dashboard(
            {
                "overall_similarity": 87,
                "text_similarity": 72,
                "ast_similarity": 94,
                "semantic_similarity": 89,
                "ai_indicator_code1": 82,
                "ai_indicator_code2": 51,
                "same_objective": "Likely",
                "same_approach": False,
                "detected_patterns": [
                    "Similar function structure",
                    "Similar loop structure",
                    "Variable names differ",
                ],
                "approach": {"code1_approach": "Iterative", "code2_approach": "Built-in function"},
                "code1": "def maximum(arr):\n    m = arr[0]\n    for x in arr:\n        if x > m:\n            m = x\n    return m",
                "code2": "def maximum(numbers):\n    return max(numbers)",
            }
        )

    with tab3:
        render_batch_dashboard(
            [
                {"pair": "student1 \u2194 student7", "similarity": 91},
                {"pair": "student2 \u2194 student5", "similarity": 84},
                {"pair": "student3 \u2194 student9", "similarity": 43},
                {"pair": "student4 \u2194 student6", "similarity": 34},
            ]
        )
