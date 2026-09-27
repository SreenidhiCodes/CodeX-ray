"""
code_viewer.py
===============
Side-by-side code display for CodeXray. Renders two code snippets next
to each other with line-level and word-level highlighting so a viewer
can see at a glance what changed (renamed variables, added/removed
lines, changed operators) — the visual counterpart to Member 3's
code_diff.py, which does the *semantic* labeling of those changes.

This module works standalone (pure difflib) so the UI isn't blocked on
code_diff.py existing yet. If code_diff.py later provides a richer
diff (e.g. explicit variable-rename pairs), pass it in via
`semantic_notes` and it will be shown alongside the visual diff instead
of replacing it.

Public API
----------
diff_lines(code1, code2) -> list[dict]
    Line-aligned diff: [{"line1": "...", "line2": "...", "status": "..."}]
    status is one of: "equal", "replace", "insert", "delete".

diff_summary(code1, code2) -> dict
    Counts: {"added": n, "removed": n, "modified": n, "unchanged": n}

render_side_by_side(code1, code2, label1="Code 1", label2="Code 2",
                     semantic_notes=None)
    Streamlit component — renders the two-column highlighted view.
    Import is local to keep this module importable without Streamlit
    installed (e.g. for the diff_lines/diff_summary unit tests).
"""

from __future__ import annotations

import difflib
import html
import re

_WORD_RE = re.compile(r"\w+|\s+|[^\w\s]")


def _split_words(line: str) -> list[str]:
    return _WORD_RE.findall(line)


def _word_level_highlight(line1: str, line2: str) -> tuple[str, str]:
    """
    For a pair of 'replace' lines, highlight only the changed words
    (e.g. a renamed variable) instead of the whole line, so
    `for x in arr:` vs `for value in numbers:` reads as two small
    highlights, not two fully-red/green lines.
    Returns (html_for_line1, html_for_line2).
    """
    w1, w2 = _split_words(line1), _split_words(line2)
    sm = difflib.SequenceMatcher(None, w1, w2, autojunk=False)
    out1, out2 = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        seg1 = html.escape("".join(w1[i1:i2]))
        seg2 = html.escape("".join(w2[j1:j2]))
        if tag == "equal":
            out1.append(seg1)
            out2.append(seg2)
        elif tag == "replace":
            out1.append(f'<mark class="cx-del">{seg1}</mark>')
            out2.append(f'<mark class="cx-add">{seg2}</mark>')
        elif tag == "delete":
            out1.append(f'<mark class="cx-del">{seg1}</mark>')
        elif tag == "insert":
            out2.append(f'<mark class="cx-add">{seg2}</mark>')
    return "".join(out1), "".join(out2)


def diff_lines(code1: str, code2: str) -> list[dict]:
    """
    Line-aligned diff between two code strings. Each entry has both
    sides even for insert/delete (the missing side is ""), so the
    caller can always render two columns in lockstep.
    """
    lines1 = code1.splitlines()
    lines2 = code2.splitlines()
    sm = difflib.SequenceMatcher(None, lines1, lines2, autojunk=False)

    rows: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for a, b in zip(lines1[i1:i2], lines2[j1:j2]):
                rows.append({"line1": a, "line2": b, "status": "equal"})
        elif tag == "replace":
            seg1, seg2 = lines1[i1:i2], lines2[j1:j2]
            for a, b in zip(seg1, seg2):
                rows.append({"line1": a, "line2": b, "status": "replace"})
            # Unequal-length replace blocks: leftover lines are pure add/remove
            for a in seg1[len(seg2):]:
                rows.append({"line1": a, "line2": "", "status": "delete"})
            for b in seg2[len(seg1):]:
                rows.append({"line1": "", "line2": b, "status": "insert"})
        elif tag == "delete":
            for a in lines1[i1:i2]:
                rows.append({"line1": a, "line2": "", "status": "delete"})
        elif tag == "insert":
            for b in lines2[j1:j2]:
                rows.append({"line1": "", "line2": b, "status": "insert"})
    return rows


def diff_summary(code1: str, code2: str) -> dict[str, int]:
    rows = diff_lines(code1, code2)
    summary = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    for r in rows:
        summary[
            {"equal": "unchanged", "replace": "modified", "insert": "added", "delete": "removed"}[r["status"]]
        ] += 1
    return summary


_CSS = """
<style>
.cx-diff-table { width: 100%; border-collapse: collapse; font-family: "Source Code Pro", monospace;
                  font-size: 0.85rem; table-layout: fixed; }
.cx-diff-table td { vertical-align: top; padding: 1px 8px; white-space: pre-wrap; word-break: break-word; }
.cx-diff-table td.ln { width: 2.2em; color: #999; text-align: right; user-select: none; padding-right: 6px; }
.cx-row-equal   td.code { background: transparent; }
.cx-row-replace td.code { background: rgba(241, 196, 15, 0.12); }
.cx-row-insert  td.code.right { background: rgba(46, 204, 113, 0.15); }
.cx-row-delete  td.code.left  { background: rgba(231, 76, 60, 0.15); }
.cx-diff-table mark.cx-add { background: rgba(46, 204, 113, 0.45); padding: 0 1px; border-radius: 2px; }
.cx-diff-table mark.cx-del { background: rgba(231, 76, 60, 0.45); padding: 0 1px; border-radius: 2px; }
</style>
"""


def render_side_by_side(
    code1: str,
    code2: str,
    label1: str = "Code 1",
    label2: str = "Code 2",
    semantic_notes: list[str] | None = None,
) -> None:
    """
    Streamlit component. `semantic_notes` (optional) is a list of
    plain-language notes from code_diff.py, e.g.
    ["arr -> numbers", "max_value -> largest"], shown above the viewer.
    """
    import streamlit as st  # local import: keeps this module testable without streamlit

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(f"**{label1}** &nbsp;vs&nbsp; **{label2}**")

    if semantic_notes:
        with st.expander("Detected renames / changes", expanded=False):
            for note in semantic_notes:
                st.markdown(f"- {note}")

    rows = diff_lines(code1, code2)
    html_rows = ['<table class="cx-diff-table">']
    n1 = n2 = 0
    for r in rows:
        status = r["status"]
        if status == "replace":
            h1, h2 = _word_level_highlight(r["line1"], r["line2"])
        else:
            h1 = html.escape(r["line1"]) if r["line1"] else ""
            h2 = html.escape(r["line2"]) if r["line2"] else ""

        if r["line1"]:
            n1 += 1
        if r["line2"]:
            n2 += 1
        ln1 = n1 if r["line1"] else ""
        ln2 = n2 if r["line2"] else ""

        html_rows.append(
            f'<tr class="cx-row-{status}">'
            f'<td class="ln">{ln1}</td><td class="code left">{h1 or "&nbsp;"}</td>'
            f'<td class="ln">{ln2}</td><td class="code right">{h2 or "&nbsp;"}</td>'
            f"</tr>"
        )
    html_rows.append("</table>")
    st.markdown("".join(html_rows), unsafe_allow_html=True)

    summary = diff_summary(code1, code2)
    st.caption(
        f"{summary['unchanged']} unchanged \u00b7 {summary['modified']} modified \u00b7 "
        f"{summary['added']} added \u00b7 {summary['removed']} removed"
    )


if __name__ == "__main__":
    a = "def maximum(arr):\n    m = arr[0]\n    for x in arr:\n        if x > m:\n            m = x\n    return m"
    b = "def maximum(numbers):\n    largest = numbers[0]\n    for value in numbers:\n        if value > largest:\n            largest = value\n    return largest"
    print(diff_summary(a, b))
    for row in diff_lines(a, b):
        print(row["status"], "|", row["line1"], "||", row["line2"])
