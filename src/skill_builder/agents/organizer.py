"""OrganizerAgent -- structures raw harvest into dynamic categories.

Reads harvested content and organizes it into meaningful categories with
source attribution. Categories are fully dynamic (no fixed list) per locked
decision. Uses Sonnet with messages.parse for Pydantic-enforced output.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.models.harvest import HarvestResult
from skill_builder.models.synthesis import CategorizedResearch
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert research organizer. Read the harvested content and organize "
    "it into meaningful categories. Categories should be dynamic -- choose whatever "
    "categories make sense for this content. Every content item must include its "
    "source URL for attribution. Be thorough: include all substantive content from "
    "the harvested pages."
)


class OrganizerAgent:
    """Organizes raw harvest into dynamic categories with source attribution.

    Conforms to BaseAgent Protocol: run(**kwargs) -> CategorizedResearch.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> CategorizedResearch:
        """Execute the organizer phase.

        Expected kwargs:
            raw_harvest: dict -- HarvestResult as dict
            brief: SkillBrief
        """
        raw_harvest: dict = kwargs["raw_harvest"]
        brief: SkillBrief = kwargs["brief"]

        # Reconstruct typed HarvestResult from dict
        harvest = HarvestResult.model_validate(raw_harvest)

        # Build the user prompt
        prompt = self._build_prompt(harvest, brief)

        logger.info(
            "OrganizerAgent: organizing %d pages for %s",
            len(harvest.pages),
            brief.name,
        )

        response = self.client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            output_format=CategorizedResearch,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result: CategorizedResearch = response.parsed_output
        logger.info(
            "OrganizerAgent: produced %d categories from %d sources",
            len(result.categories),
            result.source_count,
        )
        return result

    def _build_prompt(self, harvest: HarvestResult, brief: SkillBrief) -> str:
        """Build the user prompt with brief context and harvested content."""
        parts: list[str] = []

        # Brief context
        parts.append(f"Skill: {brief.name}")
        parts.append(f"Description: {brief.description}")
        parts.append(f"Scope: {brief.scope}")
        parts.append(f"Required capabilities: {', '.join(brief.required_capabilities)}")

        if brief.target_api_version:
            parts.append(f"Target API version: {brief.target_api_version}")

        # Harvest warnings
        if harvest.warnings:
            parts.append("\nHarvest warnings:")
            for warning in harvest.warnings:
                parts.append(f"- {warning}")

        # Page content
        parts.append(f"\n--- Harvested Content ({len(harvest.pages)} pages) ---\n")
        for page in harvest.pages:
            parts.append(f"## Source: {page.url}")
            parts.append(f"Title: {page.title}")
            parts.append(page.content)
            parts.append("")  # blank line separator

        return "\n".join(parts)
