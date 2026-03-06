"""API accuracy evaluator -- LLM-as-judge for factual API correctness.

Uses Opus via messages.parse to verify every endpoint, class name, method
name, and CLI flag in the SKILL.md against organized research data.

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
    "You are an API accuracy evaluator. Score strictly based on evidence in "
    "the research. Check every endpoint, class name, method name, and CLI flag "
    "mentioned in the skill content against the organized research data.\n\n"
    "Score 10 = all correct; 7+ = minor issues only; <7 = significant errors.\n\n"
    "Return an EvaluationDimension with:\n"
    "- name: 'api_accuracy'\n"
    "- score: 1-10 based on accuracy\n"
    "- feedback: specific issues found or confirmation of accuracy\n"
    "- passed: true if score >= 7 (you may set this but it will be overridden)\n"
)


async def evaluate_api_accuracy(
    client: Anthropic,
    skill_content: str,
    organized_research: dict,
) -> EvaluationDimension:
    """Evaluate API accuracy of a SKILL.md draft against organized research.

    Args:
        client: Anthropic client instance.
        skill_content: The full SKILL.md content string.
        organized_research: Organized research data (categorized research dict).

    Returns:
        EvaluationDimension with name="api_accuracy" and programmatic passed override.
    """
    prompt = (
        "Evaluate the API accuracy of this skill content against the research data.\n\n"
        "--- Skill Content ---\n"
        f"{skill_content}\n\n"
        "--- Organized Research ---\n"
        f"{json.dumps(organized_research, indent=2)}\n"
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
    dim = dim.model_copy(update={"name": "api_accuracy", "passed": dim.score >= 7})

    # Attach usage metadata for budget tracking
    dim._usage_meta = {  # type: ignore[attr-defined]
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    logger.info("API accuracy: score=%d passed=%s", dim.score, dim.passed)
    return dim
