"""
Anti-drift AST pins for C-20a.

After the five inline fallback sites were converted to _build_pcc_fallback,
the inline decoration pattern (⭐ Recomendación TOP + _fallback_response with
reason="empty_candidate") must exist ONLY inside the helper. Any new
occurrence outside the helper fails this guard.
"""

import ast
import re
from pathlib import Path


AI_BRAIN = Path(__file__).parent.parent / "app" / "services" / "ai_brain.py"


def _find_helper_range(tree: ast.AST) -> tuple[int, int] | None:
    """Return (start_line, end_line) of _build_pcc_fallback."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_pcc_fallback":
            return node.lineno, node.end_lineno
    return None


def _inside_helper(lineno: int, helper_range: tuple[int, int] | None) -> bool:
    if helper_range is None:
        return False
    return helper_range[0] <= lineno <= helper_range[1]


def test_pcc_fallback_empty_candidate_only_in_helper():
    """Every literal _fallback_response(reason="empty_candidate") call must
    reside inside _build_pcc_fallback."""
    src = AI_BRAIN.read_text()
    tree = ast.parse(src)
    helper_range = _find_helper_range(tree)
    assert helper_range is not None, "_build_pcc_fallback not found in ai_brain.py"

    violations: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_fallback_response"
        ):
            for kw in node.keywords:
                if (
                    kw.arg == "reason"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value == "empty_candidate"
                ):
                    if not _inside_helper(node.lineno, helper_range):
                        violations.append(node.lineno)

    assert violations == [], (
        f"_fallback_response(reason='empty_candidate') found outside "
        f"_build_pcc_fallback at lines {violations}"
    )


def test_pcc_top_recommendation_only_in_helper():
    """The literal f-string ⭐ Recomendación TOP must appear only inside
    _build_pcc_fallback (one instance)."""
    src = AI_BRAIN.read_text()
    tree = ast.parse(src)
    helper_range = _find_helper_range(tree)
    assert helper_range is not None, "_build_pcc_fallback not found in ai_brain.py"

    violations: list[int] = []
    for node in ast.walk(tree):
        # JoinedStr: f-strings; Constant (str): plain strings
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and "⭐ Recomendación TOP" in v.value:
                    if not _inside_helper(v.lineno, helper_range):
                        violations.append(v.lineno)
                elif isinstance(v, ast.FormattedValue):
                    pass  # f-string expression part, not the literal
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "⭐ Recomendación TOP" in node.value:
            if not _inside_helper(node.lineno, helper_range):
                violations.append(node.lineno)

    assert violations == [], (
        f"⭐ Recomendación TOP found outside _build_pcc_fallback at lines {violations}"
    )
