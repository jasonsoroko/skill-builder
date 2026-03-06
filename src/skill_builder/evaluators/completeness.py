"""Completeness evaluator -- LLM-as-judge for content completeness.

Uses Opus via messages.parse to verify all canonical use cases have worked
examples and all dependencies have installation commands.

Returns an EvaluationDimension with programmatic passed override (score >= 7).
"""

from __future__ import annotations

import asyncio
import json
import logging

from anthropic import Anthropic

from skill_builder.models.evaluation import EvaluationDimension
from skill_builder.resilience import retry_parse

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a completeness evaluator. Verify all canonical use cases have "
    "worked examples and all dependencies have installation commands.\n\n"
    "Score 10 = fully complete; 7+ = minor gaps; <7 = significant missing content.\n\n"
    "Return an EvaluationDimension with:\n"
    "- name: 'completeness'\n"
    "- score: 1-10 based on completeness\n"
    "- feedback: specific gaps found or confirmation of completeness\n"
    "- passed: true if score >= 7 (you may set this but it will be overridden)\n"
)


async def evaluate_completeness(
    client: Anthropic,
    skill_content: str,
    knowledge_model: dict,
) -> EvaluationDimension:
    """Evaluate completeness of a SKILL.md draft against the knowledge model.

    Args:
        client: Anthropic client instance.
        skill_content: The full SKILL.md content string.
        knowledge_model: Knowledge model dict with canonical_use_cases, dependencies, etc.

    Returns:
        EvaluationDimension with name="completeness" and programmatic passed override.
    """
    prompt = (
        "Evaluate the completeness of this skill content against the knowledge model.\n"
        "Check that every canonical use case has a worked example and every dependency "
        "has installation instructions.\n\n"
        "--- Skill Content ---\n"
        f"{skill_content}\n\n"
        "--- Knowledge Model ---\n"
        f"{json.dumps(knowledge_model, indent=2)}\n"
    )

    response = await asyncio.to_thread(
        retry_parse,
        client,
        model="claude-opus-4-6",
        max_tokens=4096,
        output_format=EvaluationDimension,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    dim: EvaluationDimension = response.parsed_output

    # Programmatic override: don't trust LLM threshold judgment
    dim = dim.model_copy(update={"name": "completeness", "passed": dim.score >= 7})

    # Attach usage metadata for budget tracking
    dim._usage_meta = {  # type: ignore[attr-defined]
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    logger.info("Completeness: score=%d passed=%s", dim.score, dim.passed)
    return dim
