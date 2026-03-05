"""Syntax evaluator -- validates Python code blocks via ast.parse.

Pure Python heuristic: no LLM calls. Extracts only ```python blocks,
ignoring bash, JSON, YAML, and other language blocks. Returns an
EvaluationDimension with pass/fail based on syntax validity.
"""

from __future__ import annotations

import ast
import re

from skill_builder.models.evaluation import EvaluationDimension


def check_syntax(skill_content: str) -> EvaluationDimension:
    """Extract Python code blocks and validate syntax via ast.parse.

    Only ```python blocks are validated. Bash, JSON, YAML, and other
    language blocks are skipped entirely.

    Args:
        skill_content: The full SKILL.md content string.

    Returns:
        EvaluationDimension with name="syntax", score, feedback, passed.
    """
    # Match ```python ... ``` blocks only
    pattern = r"```python\s*\n(.*?)```"
    blocks = re.findall(pattern, skill_content, re.DOTALL)

    errors: list[str] = []
    for i, block in enumerate(blocks, 1):
        try:
            ast.parse(block)
        except SyntaxError as e:
            errors.append(f"Block {i}: {e.msg} (line {e.lineno})")

    passed = len(errors) == 0

    if not blocks:
        feedback = "No Python code blocks found"
    elif passed:
        feedback = f"All {len(blocks)} Python blocks valid"
    else:
        feedback = "; ".join(errors)

    score = 10 if passed else max(1, 10 - len(errors) * 2)

    return EvaluationDimension(
        name="syntax",
        score=score,
        feedback=feedback,
        passed=passed,
    )
