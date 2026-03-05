"""Trigger quality evaluator -- LLM-as-judge for trigger activation quality.

Uses Opus via messages.parse to verify the trigger description is specific,
pushy, third-person, covers key terms from trigger phrases, and includes
when-to-use guidance.

Returns an EvaluationDimension with programmatic passed override (score >= 7).
"""

from __future__ import annotations

import asyncio
import json
import logging

from anthropic import Anthropic

from skill_builder.models.evaluation import EvaluationDimension

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a trigger quality evaluator. Verify the trigger description is "
    "specific, pushy, third-person, covers key terms from trigger phrases, "
    "and includes when-to-use guidance.\n\n"
    "Score 10 = excellent activation; 7+ = good; <7 = poor activation quality.\n\n"
    "Return an EvaluationDimension with:\n"
    "- name: 'trigger_quality'\n"
    "- score: 1-10 based on trigger quality\n"
    "- feedback: specific issues with the trigger or confirmation of quality\n"
    "- passed: true if score >= 7 (you may set this but it will be overridden)\n"
)


async def evaluate_trigger_quality(
    client: Anthropic,
    skill_content: str,
    knowledge_model: dict,
) -> EvaluationDimension:
    """Evaluate trigger quality of a SKILL.md draft against the knowledge model.

    Args:
        client: Anthropic client instance.
        skill_content: The full SKILL.md content string.
        knowledge_model: Knowledge model dict with trigger_phrases.

    Returns:
        EvaluationDimension with name="trigger_quality" and programmatic passed override.
    """
    prompt = (
        "Evaluate the trigger quality of this skill's YAML frontmatter description.\n"
        "Check that the trigger description is specific, pushy, third-person, "
        "covers key terms from the trigger phrases, and includes when-to-use guidance.\n\n"
        "--- Skill Content ---\n"
        f"{skill_content}\n\n"
        "--- Knowledge Model ---\n"
        f"{json.dumps(knowledge_model, indent=2)}\n"
    )

    response = await asyncio.to_thread(
        client.messages.parse,
        model="claude-opus-4-6",
        max_tokens=4096,
        output_format=EvaluationDimension,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    dim: EvaluationDimension = response.parsed_output

    # Programmatic override: don't trust LLM threshold judgment
    dim = dim.model_copy(update={"name": "trigger_quality", "passed": dim.score >= 7})

    # Attach usage metadata for budget tracking
    dim._usage_meta = {  # type: ignore[attr-defined]
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    logger.info("Trigger quality: score=%d passed=%s", dim.score, dim.passed)
    return dim
