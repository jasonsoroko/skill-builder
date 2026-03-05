"""MapperAgent -- translates KnowledgeModel into a draft SKILL.md.

Produces a structured SkillDraft with YAML frontmatter (pushy trigger description),
worked examples for all canonical use cases, an explicit DO/DON'T section, and
optional reference_files for large sections that exceed the 500-line budget.

Uses Sonnet with messages.parse for Pydantic-enforced output.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.models.brief import SkillBrief
from skill_builder.models.production import SkillDraft
from skill_builder.models.synthesis import KnowledgeModel
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert skill author for Claude Code. You translate structured knowledge "
    "into a high-quality SKILL.md file.\n\n"
    "CRITICAL RULES:\n"
    "1. Keep the SKILL.md content UNDER 500 lines. This is a hard budget. If content "
    "would exceed 500 lines, extract large reference sections (API tables, extensive "
    "examples, configuration references) into reference_files (filename -> content). "
    "Use progressive disclosure: most important info first, reference material last "
    "or extracted to references/.\n\n"
    "2. Include YAML frontmatter at the top with:\n"
    "   - name: lowercase-hyphenated identifier (max 64 chars)\n"
    "   - description: third-person, specific, pushy trigger description. Include key "
    "terms from trigger_phrases. Describe WHAT the skill does AND WHEN to use it. "
    "Must be under 1024 characters.\n\n"
    "3. Include WORKED EXAMPLES for ALL canonical use cases. Each example must be a "
    "complete, runnable snippet: imports, setup, execution, and output handling. "
    "Copy-pasteable.\n\n"
    "4. Include an explicit DO/DON'T section derived from the gotchas and anti-patterns "
    "in the knowledge model. Tell Claude what to avoid and what to do instead.\n\n"
    "5. Set line_count to the actual number of lines in the content field.\n"
    "6. Set has_frontmatter to true if YAML frontmatter is present.\n"
)


class MapperAgent:
    """Translates KnowledgeModel into a draft SKILL.md.

    Conforms to BaseAgent Protocol: run(**kwargs) -> SkillDraft.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> SkillDraft:
        """Execute the mapper phase.

        Expected kwargs:
            knowledge_model: dict -- KnowledgeModel as dict
            brief: SkillBrief
            failed_dimensions: list[dict] | None -- evaluation feedback for re-production
        """
        knowledge_model: dict = kwargs["knowledge_model"]
        brief: SkillBrief = kwargs["brief"]
        failed_dimensions: list[dict] | None = kwargs.get("failed_dimensions")

        km = KnowledgeModel.model_validate(knowledge_model)
        prompt = self._build_prompt(km, brief, failed_dimensions)

        logger.info(
            "MapperAgent: drafting SKILL.md for %s with %d use cases",
            brief.name,
            len(km.canonical_use_cases),
        )

        response = self.client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            output_format=SkillDraft,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result: SkillDraft = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        logger.info(
            "MapperAgent: produced %d-line draft (frontmatter=%s, refs=%s)",
            result.line_count,
            result.has_frontmatter,
            "yes" if result.reference_files else "no",
        )
        return result

    def _build_prompt(
        self,
        km: KnowledgeModel,
        brief: SkillBrief,
        failed_dimensions: list[dict] | None = None,
    ) -> str:
        """Build the user prompt with knowledge model, brief, and optional fix feedback."""
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

        # Knowledge model
        parts.append("\n--- Knowledge Model ---")
        parts.append(json.dumps(km.model_dump(), indent=2))

        # Canonical use cases explicitly listed for worked examples
        parts.append("\n--- Canonical Use Cases (each needs a worked example) ---")
        for i, use_case in enumerate(km.canonical_use_cases, 1):
            parts.append(f"{i}. {use_case}")

        # Trigger phrases for frontmatter description
        parts.append("\n--- Trigger Phrases (include key terms in description) ---")
        for phrase in km.trigger_phrases:
            parts.append(f"- {phrase}")

        # DO/DON'T source material
        parts.append("\n--- Gotchas (use for DON'T section) ---")
        for gotcha in km.common_gotchas:
            parts.append(f"- {gotcha}")

        parts.append("\n--- Anti-Patterns (use for DON'T section) ---")
        for anti in km.anti_patterns:
            parts.append(f"- {anti}")

        parts.append("\n--- Best Practices (use for DO section) ---")
        for bp in km.best_practices:
            parts.append(f"- {bp}")

        # Re-production feedback (only failed dimensions)
        if failed_dimensions:
            parts.append("\n--- FIX THESE ISSUES ---")
            parts.append("The previous draft failed evaluation. Fix ONLY these issues:")
            for dim in failed_dimensions:
                name = dim.get("name", "unknown")
                feedback = dim.get("feedback", "no feedback")
                parts.append(f"- {name}: {feedback}")

        return "\n".join(parts)
