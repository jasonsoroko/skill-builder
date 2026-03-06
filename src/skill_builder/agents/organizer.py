"""OrganizerAgent -- structures raw harvest into dynamic categories.

Reads harvested content and organizes it into meaningful categories with
source attribution. Categories are fully dynamic (no fixed list) per locked
decision. Uses Sonnet with messages.parse for Pydantic-enforced output.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.models.harvest import HarvestResult
from skill_builder.models.synthesis import CategorizedResearch
from skill_builder.resilience import retry_parse
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

        response = retry_parse(
            self.client,
            model="claude-sonnet-4-6",
            max_tokens=16384,
            output_format=CategorizedResearch,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result: CategorizedResearch = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        logger.info(
            "OrganizerAgent: produced %d categories from %d sources",
            len(result.categories),
            result.source_count,
        )
        return result

    # Budget ~150K tokens for content = ~600K chars.
    # Reserve ~2K chars for brief context and overhead.
    _MAX_PROMPT_CHARS = 600_000

    def _build_prompt(self, harvest: HarvestResult, brief: SkillBrief) -> str:
        """Build the user prompt with brief context and harvested content.

        Truncates per-page content proportionally so the total prompt fits
        within the model's context window.
        """
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

        # Calculate per-page budget to stay within context window.
        # When page count is extreme (>2990), overhead alone exceeds the budget;
        # the max(500, ...) floor still applies but total may exceed the cap,
        # so we hard-truncate the final prompt as a backstop.
        n_pages = len(harvest.pages)
        overhead = 200 * n_pages  # url + title headers per page
        content_budget = self._MAX_PROMPT_CHARS - 2000 - overhead
        per_page_limit = max(500, content_budget // max(n_pages, 1))

        # Page content
        parts.append(f"\n--- Harvested Content ({n_pages} pages) ---\n")
        for page in harvest.pages:
            parts.append(f"## Source: {page.url}")
            parts.append(f"Title: {page.title}")
            content = page.content
            if len(content) > per_page_limit:
                content = content[:per_page_limit] + "\n[... truncated ...]"
            parts.append(content)
            parts.append("")  # blank line separator

        prompt = "\n".join(parts)
        if len(prompt) > self._MAX_PROMPT_CHARS:
            prompt = prompt[: self._MAX_PROMPT_CHARS] + "\n[... prompt truncated ...]"
        return prompt
