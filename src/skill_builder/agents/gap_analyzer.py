"""GapAnalyzerAgent -- cross-references research against required capabilities.

Uses Opus with adaptive thinking to analyze whether organized research covers
all required capabilities from the brief. If any capability is missing or
severely underrepresented, marks is_sufficient=False and provides specific
search queries to fill the gaps.

CRITICAL: Does NOT use tool_choice with adaptive thinking. Uses messages.parse
with output_format instead (compatible with adaptive thinking per RESEARCH.md).

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.models.synthesis import CategorizedResearch, GapReport
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are analyzing research completeness for a skill. For EACH required "
    "capability, determine if the research contains sufficient information. "
    "If ANY required capability is completely missing or severely "
    "underrepresented, set is_sufficient=False. For each gap, provide a "
    "specific search query that would fill it."
)


class GapAnalyzerAgent:
    """Analyzes research completeness against required capabilities.

    Conforms to BaseAgent Protocol: run(**kwargs) -> GapReport.

    Uses Opus with adaptive thinking for thorough gap analysis.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> GapReport:
        """Execute the gap analysis phase.

        Expected kwargs:
            categorized_research: dict -- CategorizedResearch as dict
            brief: SkillBrief
            harvest_warnings: list[str] (optional)
        """
        categorized_research: dict = kwargs["categorized_research"]
        brief: SkillBrief = kwargs["brief"]
        harvest_warnings: list[str] = kwargs.get("harvest_warnings", [])

        # Reconstruct typed CategorizedResearch from dict
        research = CategorizedResearch.model_validate(categorized_research)

        # Build the user prompt
        prompt = self._build_prompt(research, brief, harvest_warnings)

        logger.info(
            "GapAnalyzerAgent: analyzing %d categories against %d capabilities for %s",
            len(research.categories),
            len(brief.required_capabilities),
            brief.name,
        )

        response = self.client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_format=GapReport,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Check for output truncation (Pitfall 6)
        if response.stop_reason == "max_tokens":
            logger.warning(
                "GapAnalyzerAgent: response truncated (stop_reason=max_tokens). "
                "Output may be incomplete."
            )

        result: GapReport = response.parsed_output
        logger.info(
            "GapAnalyzerAgent: is_sufficient=%s, %d gaps found",
            result.is_sufficient,
            len(result.identified_gaps),
        )
        return result

    def _build_prompt(
        self,
        research: CategorizedResearch,
        brief: SkillBrief,
        harvest_warnings: list[str],
    ) -> str:
        """Build the user prompt with capabilities and research."""
        parts: list[str] = []

        parts.append(f"Skill: {brief.name}")
        parts.append(f"Target use case: {brief.scope}")
        parts.append(f"Tool category: {brief.tool_category}")
        parts.append(
            f"Target API version: {brief.target_api_version or 'latest'}"
        )

        # List every required capability explicitly (SYNTH-04)
        parts.append("\nRequired capabilities (check EACH one):")
        for i, cap in enumerate(brief.required_capabilities, 1):
            parts.append(f"  {i}. {cap}")

        # Harvest warnings
        if harvest_warnings:
            parts.append(
                "\nHarvest warnings (version conflicts, missing data):"
            )
            for warning in harvest_warnings:
                parts.append(f"- {warning}")
        else:
            parts.append("\nHarvest warnings: None")

        # Full categorized research as JSON
        parts.append("\nOrganized research:")
        parts.append(json.dumps(research.model_dump(), indent=2))

        return "\n".join(parts)
