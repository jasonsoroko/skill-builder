"""DocumenterAgent -- produces a SETUP.md draft from a KnowledgeModel.

Generates setup documentation with prerequisites, API key configuration,
quick start guide, and troubleshooting tips. Uses Sonnet with messages.parse
for Pydantic-enforced output.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.models.production import SetupDraft
from skill_builder.models.synthesis import KnowledgeModel
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert technical writer for Claude Code skills. You produce clear, "
    "actionable SETUP.md documentation.\n\n"
    "Your SETUP.md MUST include these sections:\n"
    "1. Prerequisites -- required software, versions, and system requirements\n"
    "2. API Keys and Environment Variables -- every key needed, how to obtain it, "
    "where to set it (export, .env, etc.)\n"
    "3. Quick Start -- minimal steps to get the skill working (install, configure, verify)\n"
    "4. Top 3 Troubleshooting Tips -- the most common setup issues and their fixes\n\n"
    "Keep instructions concrete and copy-pasteable. Use code blocks for commands.\n"
    "Set has_prerequisites to true if the prerequisites section is present.\n"
    "Set has_quick_start to true if the quick start section is present.\n"
)


class DocumenterAgent:
    """Produces a SETUP.md draft from a KnowledgeModel.

    Conforms to BaseAgent Protocol: run(**kwargs) -> SetupDraft.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> SetupDraft:
        """Execute the documenter phase.

        Expected kwargs:
            knowledge_model: dict -- KnowledgeModel as dict
            brief: SkillBrief
        """
        knowledge_model: dict = kwargs["knowledge_model"]
        brief: SkillBrief = kwargs["brief"]

        km = KnowledgeModel.model_validate(knowledge_model)
        prompt = self._build_prompt(km, brief)

        logger.info(
            "DocumenterAgent: drafting SETUP.md for %s",
            brief.name,
        )

        response = self.client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            output_format=SetupDraft,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result: SetupDraft = response.parsed_output
        logger.info(
            "DocumenterAgent: produced setup draft (prerequisites=%s, quick_start=%s)",
            result.has_prerequisites,
            result.has_quick_start,
        )
        return result

    def _build_prompt(self, km: KnowledgeModel, brief: SkillBrief) -> str:
        """Build the user prompt with knowledge model and brief context."""
        parts: list[str] = []

        # Brief context
        parts.append(f"Skill: {brief.name}")
        parts.append(f"Description: {brief.description}")
        parts.append(f"Scope: {brief.scope}")
        parts.append(f"Tool category: {brief.tool_category}")
        parts.append(f"Required capabilities: {', '.join(brief.required_capabilities)}")
        parts.append(f"Deploy target: {brief.deploy_target}")

        if brief.target_api_version:
            parts.append(f"Target API version: {brief.target_api_version}")

        # Dependencies for prerequisites
        parts.append("\n--- Dependencies ---")
        for dep in km.dependencies:
            parts.append(f"- {dep}")

        # Required parameters for API keys section
        parts.append("\n--- Required Parameters ---")
        for param in km.required_parameters:
            parts.append(f"- {param}")

        # Minimum viable example for quick start
        parts.append("\n--- Minimum Viable Example ---")
        parts.append(km.minimum_viable_example)

        # Common gotchas for troubleshooting tips
        parts.append("\n--- Common Gotchas (source for troubleshooting tips) ---")
        for gotcha in km.common_gotchas:
            parts.append(f"- {gotcha}")

        # Full knowledge model for additional context
        parts.append("\n--- Full Knowledge Model ---")
        parts.append(json.dumps(km.model_dump(), indent=2))

        return "\n".join(parts)
