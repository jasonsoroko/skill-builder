"""Compactness evaluator -- checks SKILL.md is under 500 lines.

Pure Python heuristic: no LLM calls. Returns an EvaluationDimension
with pass/fail based on line count.
"""

from __future__ import annotations

from skill_builder.models.evaluation import EvaluationDimension


def check_compactness(skill_content: str) -> EvaluationDimension:
    """Check SKILL.md is under 500 lines.

    Args:
        skill_content: The full SKILL.md content string.

    Returns:
        EvaluationDimension with name="compactness", score, feedback, passed.
    """
    line_count = skill_content.count("\n") + 1
    passed = line_count <= 500
    score = 10 if passed else max(1, 10 - (line_count - 500) // 50)
    feedback = f"{line_count} lines" + (
        "" if passed else f" (exceeds 500-line limit by {line_count - 500})"
    )

    return EvaluationDimension(
        name="compactness",
        score=score,
        feedback=feedback,
        passed=passed,
    )
