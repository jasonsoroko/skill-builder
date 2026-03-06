"""LearnerAgent -- distills organized research into a structured KnowledgeModel.

Extracts canonical use cases, required parameters, gotchas, best practices,
anti-patterns, dependencies, minimum viable example, and trigger phrases from
organized research and gap report. Uses Sonnet with messages.parse for
Pydantic-enforced output.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.resilience import retry_parse
from skill_builder.models.synthesis import (
    CategorizedResearch,
    GapReport,
    KnowledgeModel,
)
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert at distilling research into structured knowledge. "
    "Extract the key information from the organized research into a structured "
    "knowledge model. Be thorough and specific -- this knowledge model drives "
    "the production of a skill file."
)


class LearnerAgent:
    """Distills organized research into a structured KnowledgeModel.

    Conforms to BaseAgent Protocol: run(**kwargs) -> KnowledgeModel.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> KnowledgeModel:
        """Execute the learner phase.

        Expected kwargs:
            categorized_research: dict -- CategorizedResearch as dict
            gap_report: dict -- GapReport as dict
            brief: SkillBrief
        """
        categorized_research: dict = kwargs["categorized_research"]
        gap_report: dict = kwargs["gap_report"]
        brief: SkillBrief = kwargs["brief"]

        # Reconstruct typed models from dicts
        research = CategorizedResearch.model_validate(categorized_research)
        gaps = GapReport.model_validate(gap_report)

        # Build the user prompt
        prompt = self._build_prompt(research, gaps, brief)

        logger.info(
            "LearnerAgent: distilling knowledge from %d categories for %s",
            len(research.categories),
            brief.name,
        )

        response = retry_parse(
            self.client,
            model="claude-sonnet-4-6",
            max_tokens=8192,
            output_format=KnowledgeModel,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result: KnowledgeModel = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        logger.info(
            "LearnerAgent: extracted %d use cases, %d gotchas, %d best practices",
            len(result.canonical_use_cases),
            len(result.common_gotchas),
            len(result.best_practices),
        )
        return result

    def _build_prompt(
        self,
        research: CategorizedResearch,
        gaps: GapReport,
        brief: SkillBrief,
    ) -> str:
        """Build the user prompt with research, gaps, and brief context."""
        parts: list[str] = []

        # Brief context
        parts.append(f"Skill: {brief.name}")
        parts.append(f"Description: {brief.description}")
        parts.append(f"Scope: {brief.scope}")
        parts.append(f"Tool category: {brief.tool_category}")
        parts.append(f"Required capabilities: {', '.join(brief.required_capabilities)}")

        if brief.target_api_version:
            parts.append(f"Target API version: {brief.target_api_version}")

        # Gap report context
        parts.append("\n--- Gap Report ---")
        if gaps.is_sufficient:
            parts.append("Research coverage: SUFFICIENT")
        else:
            parts.append("Research coverage: INSUFFICIENT")
            if gaps.identified_gaps:
                parts.append("Known gaps (acknowledge in knowledge model):")
                for gap in gaps.identified_gaps:
                    parts.append(f"  - {gap}")

        # Full categorized research
        parts.append("\n--- Organized Research ---")
        parts.append(json.dumps(research.model_dump(), indent=2))

        return "\n".join(parts)
