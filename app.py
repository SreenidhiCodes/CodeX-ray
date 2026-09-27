"""Streamlit interface for CodeXray."""
from __future__ import annotations

import ast
import csv
import io
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ai_detector import predict_ai_likelihood
from ast_analyzer import CodeParseError, normalize_code
from code_diff import compare_diff
from code_metrics import calculate_metrics
from report_generator import generate_report
from similarity_engine import compare_codes
import code_viewer
import dashboard


st.set_page_config(page_title="CodeXray", page_icon="🔍", layout="wide")
st.markdown("""
<style>
.main-title {font-size:46px;font-weight:800;margin-bottom:5px}
.subtitle {font-size:20px;font-weight:500;margin-bottom:30px}
.feature-box {padding:22px;border-radius:14px;border:1px solid #4a6fa5;background:#172b4d;min-height:180px}
.feature-box h3,.feature-box p {color:#fff!important}
.feature-box p {font-size:16px;line-height:1.6}
.section-title {font-size:28px;font-weight:700;margin:30px 0 18px}
</style>
""", unsafe_allow_html=True)


def read_upload(upload) -> str:
    """Decode Python source permissively so unusual bytes never crash a page."""
    raw = upload.getvalue()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def syntax_error(code: str):
    try:
        ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return exc
    return None


def metrics_or_basic(code: str) -> dict:
    try:
        return calculate_metrics(code)
    except (SyntaxError, ValueError, RecursionError):
        lines = code.splitlines()
        return {"lines_of_code": sum(bool(line.strip()) for line in lines),
                "total_lines": len(lines), "blank_lines": sum(not line.strip() for line in lines),
                "functions": 0, "loops": 0, "conditions": 0, "variables": 0,
                "imports": 0, "classes": 0, "complexity": None}


def add_downloads(stem: str, payload: dict, *, pair_rows: list[dict] | None = None) -> None:
    st.markdown("#### Download report")
    c1, c2, c3 = st.columns(3)
    pretty = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    c1.download_button("JSON", pretty, f"{stem}.json", "application/json", key=f"{stem}_json")
    markdown = "# CodeXray report\n\n```json\n" + pretty + "\n```\n"
    c2.download_button("Markdown", markdown, f"{stem}.md", "text/markdown", key=f"{stem}_md")
    if pair_rows is None:
        pair_rows = [{"metric": key, "value": json.dumps(value, ensure_ascii=False, default=str)}
                     for key, value in payload.items()]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["pair", "similarity", "metric", "value"])
    writer.writeheader()
    for row in pair_rows:
        writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
    c3.download_button("CSV", output.getvalue(), f"{stem}.csv", "text/csv", key=f"{stem}_csv")


def show_validation(label: str, code: str) -> bool:
    err = syntax_error(code)
    if err:
        st.warning(f"{label} has invalid or incomplete Python syntax (line {getattr(err, 'lineno', '?')}): {err.msg if hasattr(err, 'msg') else err}. CodeXray will still compare source and token patterns; AST and approach analysis need valid syntax.")
        return False
    return True


def add_engine_result(payload: dict, engine: dict) -> None:
    components = engine.get("component_scores", {})
    payload["overall_similarity"] = engine.get("overall_similarity_pct", 0)
    payload["comparison_mode"] = engine.get("comparison_mode", "full_analysis")
    payload["comparison_notice"] = engine.get("comparison_notice")
    payload["component_scores"] = components
    payload["evidence"] = engine.get("evidence", [])
    payload["approach_analysis"] = engine.get("approach_analysis", {})
    payload["semantic_available"] = engine.get("semantic_available", False)
    payload["semantic_requested"] = engine.get("semantic_requested", False)
    payload["text_similarity"] = components.get("text_similarity")
    payload["ast_similarity"] = components.get("ast_similarity")
    payload["semantic_similarity"] = components.get("semantic_similarity")
    payload["fingerprint_similarity"] = components.get("fingerprint_similarity")
    payload["control_flow_similarity"] = components.get("control_flow_similarity")
    payload["syntax_token_similarity"] = components.get("syntax_token_similarity")
    payload["similarity_available"] = True


st.sidebar.title("🔍 CodeXray")
st.sidebar.caption("AI-Powered Python Code Analysis")
page = st.sidebar.radio("Navigation", ["Home", "Analyze Code", "Compare Codes", "Batch Analysis", "About"])
st.sidebar.caption("Python Code Analysis & Similarity Detection")


if page == "Home":
    st.markdown('<div class="main-title">🔍 CODEXRAY</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">AI-Powered Python Code Analysis and Similarity Detection</div>', unsafe_allow_html=True)
    st.info("Analyze Python programs, compare code similarity, inspect differences, and run batch analysis.")
    st.markdown('<div class="section-title">What CodeXray Can Do</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, title, body in zip(cols, ["🧩 Code Analysis", "🔎 Similarity Detection", "📊 Batch Analysis"],
                                ["Inspect normalized structure and code statistics.", "Compare programs with text, AST, control-flow, and semantic signals.", "Upload multiple Python programs and compare them automatically."]):
        col.markdown(f'<div class="feature-box"><h3>{title}</h3><p>{body}</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Analysis Techniques</div>', unsafe_allow_html=True)
    cs = st.columns(4)
    for col, name in zip(cs, ["AST", "Text similarity", "Control flow", "Logic fingerprint"]):
        col.metric(name, "Enabled")

elif page == "Analyze Code":
    st.header("🧩 Analyze Python Code")
    code = st.text_area("Enter Python Code", height=300, placeholder="Write or paste Python code here...")
    uploaded = st.file_uploader("Or upload a Python file", type=["py"], key="analyze_upload")
    if uploaded:
        code = read_upload(uploaded)
        st.code(code, language="python")
    if st.button("🔍 Analyze Code", type="primary"):
        if not code.strip():
            st.warning("Please enter or upload Python code.")
        else:
            valid = show_validation("Code", code)
            result = {"filename": uploaded.name if uploaded else "pasted_code.py", "statistics": metrics_or_basic(code), "code": code}
            if valid:
                try:
                    result["normalized_code"] = normalize_code(code)
                    ai = predict_ai_likelihood(code)
                    result["ai_analysis"] = ai
                    result["ai_indicator"] = ai.get("score", 0)
                    result["ai_method"] = ai.get("method", "heuristic")
                    result["ai_confidence"] = ai.get("confidence")
                    result["indicators"] = ai.get("indicators", [])
                except (CodeParseError, SyntaxError, ValueError) as exc:
                    st.warning(f"Some structural analysis was unavailable: {exc}")
            else:
                ai = predict_ai_likelihood(code)
                result["ai_analysis"] = ai
                result["ai_indicator"] = ai.get("score", 0)
                result["ai_method"] = ai.get("method", "heuristic")
                result["ai_confidence"] = ai.get("confidence", "low")
                result["indicators"] = ai.get("indicators", [])
            st.session_state["codexray_analysis_result"] = result
    if st.session_state.get("codexray_analysis_result"):
        result = st.session_state["codexray_analysis_result"]
        st.success("Analysis completed.")
        if result.get("normalized_code") is not None:
            with st.expander("Normalized code", expanded=True):
                st.code(result["normalized_code"], language="python")
        dashboard.render_single_code_dashboard(result)
        add_downloads("codexray_analysis", result)

elif page == "Compare Codes":
    st.header("🔎 Compare Two Python Programs")
    st.write("Paste two programs or upload Python files to compare similarity and inspect their differences.")
    use_codebert = st.checkbox("Enable optional CodeBERT semantic scoring", help="Requires torch and transformers and downloads the model the first time. Local comparison signals work without it.")
    l, r = st.columns(2)
    with l: file1 = st.file_uploader("Upload Code 1 (.py)", type=["py"], key="compare_file1")
    with r: file2 = st.file_uploader("Upload Code 2 (.py)", type=["py"], key="compare_file2")
    l, r = st.columns(2)
    with l: code1 = st.text_area("Code 1", height=300, key="code1")
    with r: code2 = st.text_area("Code 2", height=300, key="code2")
    if file1: code1 = read_upload(file1)
    if file2: code2 = read_upload(file2)
    if st.button("🔍 Compare Code", type="primary"):
        if not code1.strip() or not code2.strip():
            st.warning("Please provide both Python programs.")
        else:
            valid1, valid2 = show_validation("Code 1", code1), show_validation("Code 2", code2)
            payload = {"code1": code1, "code2": code2, "code1_statistics": metrics_or_basic(code1), "code2_statistics": metrics_or_basic(code2), "similarity_available": False}
            try:
                diff = compare_diff(code1, code2).to_dict()
                payload["diff"] = diff
                st.subheader("Code differences")
                code_viewer.render_side_by_side(code1, code2)
                st.json({"unchanged_ratio": diff.get("unchanged_ratio"), "added_lines": len(diff.get("added_lines", [])), "deleted_lines": len(diff.get("deleted_lines", [])), "modified_lines": len(diff.get("modified_lines", [])), "changed_variables": diff.get("changed_variables", {})})
            except Exception as exc:
                st.warning(f"Diff details are unavailable: {exc}")
            if valid1 and valid2:
                try:
                    detailed = generate_report(code1, code2)
                    engine = compare_codes(code1, code2, use_semantic=use_codebert)
                    payload.update(detailed)
                    payload["code1"], payload["code2"] = code1, code2
                    payload["report_generator_overall_similarity"] = detailed.get("overall_similarity")
                    payload["approach_semantic_similarity"] = detailed.get("semantic_similarity")
                    add_engine_result(payload, engine)
                    payload["ai_indicator_details"] = {}
                    for key in ("ai_indicator_code1", "ai_indicator_code2"):
                        indicator = payload.get(key)
                        if isinstance(indicator, dict):
                            payload["ai_indicator_details"][key] = dict(indicator)
                            payload[key] = indicator.get("score", 0) / 100
                    # Dashboard expects fractional component scores and concise approach labels.
                    detail = detailed.get("approach_detail", {})
                    payload["approach"] = {
                        "code1_approach": detail.get("approach_1", {}).get("label"),
                        "code2_approach": detail.get("approach_2", {}).get("label"),
                        "notes": [detail["notes"]] if detail.get("notes") else [],
                    }
                except (CodeParseError, SyntaxError, ValueError, RecursionError) as exc:
                    st.warning(f"Comparison could not complete: {exc}")
                    engine = compare_codes(code1, code2, use_semantic=use_codebert)
                    add_engine_result(payload, engine)
            else:
                engine = compare_codes(code1, code2)
                add_engine_result(payload, engine)
                payload["ai_indicator_details"] = {}
                for label, source in (("ai_indicator_code1", code1), ("ai_indicator_code2", code2)):
                    indicator = predict_ai_likelihood(source)
                    payload["ai_indicator_details"][label] = indicator
                    payload[label] = indicator.get("score", 0)
                payload["same_objective"] = "Uncertain"
                payload["same_approach"] = None
                payload["approach"] = {
                    "code1_approach": "Unavailable until syntax is valid",
                    "code2_approach": "Unavailable until syntax is valid",
                    "notes": [engine.get("comparison_notice", "Approach analysis requires valid Python syntax.")],
                }
            st.session_state["codexray_comparison_result"] = payload
    if st.session_state.get("codexray_comparison_result"):
        payload = st.session_state["codexray_comparison_result"]
        st.subheader("Code statistics")
        stat1, stat2 = st.columns(2)
        with stat1:
            st.markdown("**Code 1**")
            st.json(payload.get("code1_statistics", {}))
        with stat2:
            st.markdown("**Code 2**")
            st.json(payload.get("code2_statistics", {}))
        if payload.get("similarity_available"):
            dashboard.render_comparison_dashboard(payload)
        add_downloads("codexray_comparison", payload)

elif page == "Batch Analysis":
    st.header("📊 Batch Analysis")
    st.write("Upload multiple Python files to analyze them and compare every pair.")
    use_codebert = st.checkbox("Enable optional CodeBERT semantic scoring", help="Requires torch and transformers and downloads the model the first time. Local comparison signals work without it.")
    files = st.file_uploader("Upload Python files", type=["py"], accept_multiple_files=True, key="batch_upload")
    if not files:
        st.info("Upload Python files above to begin batch analysis.")
    else:
        codes = {f.name: read_upload(f) for f in files}
        st.success(f"Uploaded {len(codes)} file(s).")
        payload = {"files": {name: {"statistics": metrics_or_basic(text), "syntax_valid": syntax_error(text) is None} for name, text in codes.items()}, "pairs": []}
        st.subheader("File statistics")
        st.dataframe([{"file": name, **details["statistics"], "syntax_valid": details["syntax_valid"]}
                      for name, details in payload["files"].items()], width="stretch", hide_index=True)
        for name, text in codes.items():
            with st.expander(f"{name} — normalized source"):
                if syntax_error(text):
                    show_validation(name, text)
                    st.code(text, language="python")
                else:
                    try: st.code(normalize_code(text), language="python")
                    except (CodeParseError, ValueError) as exc: st.warning(str(exc)); st.code(text, language="python")
        names = list(codes)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                row = {"pair": f"{a} ↔ {b}", "similarity": None}
                try:
                    comparison = compare_codes(codes[a], codes[b], use_semantic=use_codebert)
                    row["similarity"] = comparison.get("overall_similarity_pct", 0)
                    row["components"] = comparison.get("component_scores", {})
                    row["evidence"] = comparison.get("evidence", [])
                    row["comparison_mode"] = comparison.get("comparison_mode", "full_analysis")
                    row["comparison_notice"] = comparison.get("comparison_notice")
                except (CodeParseError, SyntaxError, ValueError, RecursionError) as exc:
                    row["error"] = str(exc)
                payload["pairs"].append(row)
        dashboard.render_batch_dashboard([p for p in payload["pairs"] if p["similarity"] is not None])
        st.subheader("Pairwise details")
        for item in payload["pairs"]:
            with st.expander(item["pair"]):
                if item["similarity"] is None: st.warning(item.get("error", "Comparison unavailable."))
                else:
                    if item.get("comparison_notice"):
                        st.warning(item["comparison_notice"])
                    st.metric("Overall similarity", f"{item['similarity']}%")
                    st.json(item.get("components", {}))
                    if item.get("evidence"): st.write("Evidence: " + "; ".join(item["evidence"]))
        add_downloads("codexray_batch", payload, pair_rows=[{"pair": p["pair"], "similarity": p.get("similarity"), "metric": p.get("comparison_mode", ""), "value": p.get("comparison_notice", p.get("error", ""))} for p in payload["pairs"]])

else:
    st.header("ℹ️ About CodeXray")
    st.write("CodeXray analyzes Python code and compares programs using text, AST, control-flow, fingerprint, and approach signals.")
    st.markdown("- Python code analysis and normalization\n- AI-generation likelihood indicator\n- Pairwise and batch similarity\n- Side-by-side differences and downloadable JSON, Markdown, and CSV reports")
