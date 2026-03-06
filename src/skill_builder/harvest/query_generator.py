"""LLM-generated search queries with template fallback.

Generates targeted Exa (semantic) and Tavily (factual) search queries
per required capability using Anthropic's messages.parse() for structured output.
Falls back to template-based queries when LLM calls fail.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from skill_builder.models.brief import SkillBrief
from skill_builder.models.synthesis import GeneratedQueries
from skill_builder.resilience import retry_parse

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = logging.getLogger(__name__)


def template_fallback_queries(brief: SkillBrief) -> GeneratedQueries:
    """Build template search queries from brief fields.

    Produces one Exa query (semantic/conceptual) and one Tavily query
    (factual/current) per required capability.

    Args:
        brief: The skill brief containing name and required_capabilities.

    Returns:
        GeneratedQueries with template-based queries.
    """
    exa_queries = [
        f"{brief.name} {capability} best practices examples"
        for capability in brief.required_capabilities
    ]
    tavily_queries = [
        f"{brief.name} {capability} common errors gotchas"
        for capability in brief.required_capabilities
    ]
    return GeneratedQueries(exa_queries=exa_queries, tavily_queries=tavily_queries)


def generate_search_queries(client: Anthropic, brief: SkillBrief) -> GeneratedQueries:
    """Generate search queries via LLM with template fallback.

    Uses Anthropic's messages.parse() with Sonnet to produce targeted
    Exa and Tavily queries for each required capability.

    Falls back to template_fallback_queries on any exception.

    Args:
        client: Anthropic client instance.
        brief: The skill brief to generate queries for.

    Returns:
        GeneratedQueries with LLM-generated or fallback template queries.
    """
    prompt = f"""Generate targeted search queries for researching this tool/skill.

Tool: {brief.name}
Description: {brief.description}
Required capabilities: {', '.join(brief.required_capabilities)}
Scope: {brief.scope}

Generate one Exa query per required capability
(semantic/conceptual: best practices, patterns, usage examples).
Generate one Tavily query per required capability
(factual/current: error messages, version issues, gotchas).
"""
    try:
        response = retry_parse(
            client,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            output_format=GeneratedQueries,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return result
    except Exception:
        logger.warning(
            "LLM query generation failed, falling back to template queries",
            exc_info=True,
        )
        return template_fallback_queries(brief)


def refine_gap_queries(
    client: Anthropic,
    brief: SkillBrief,
    raw_queries: list[str],
) -> GeneratedQueries:
    """Refine gap-closure queries through LLM for better search optimization.

    Takes the Gap Analyzer's recommended_search_queries and produces
    search-optimized Exa/Tavily queries via LLM.

    Per locked decision: pass the Gap Analyzer's recommended_search_queries
    through the LLM query generator to produce better search-optimized
    queries before running them.

    Falls back to template queries on error.

    Args:
        client: Anthropic client instance.
        brief: The skill brief for context.
        raw_queries: Gap Analyzer's recommended search queries.

    Returns:
        GeneratedQueries with refined or fallback queries.
    """
    prompt = f"""Optimize these research gap queries into targeted search queries.

Tool: {brief.name}
Description: {brief.description}
Required capabilities: {', '.join(brief.required_capabilities)}

Raw gap queries to refine:
{chr(10).join(f'- {q}' for q in raw_queries)}

For each gap query, produce:
- One Exa query (semantic/conceptual: best practices, patterns, usage examples)
- One Tavily query (factual/current: error messages, version-specific issues, gotchas)
"""
    try:
        response = retry_parse(
            client,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            output_format=GeneratedQueries,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return result
    except Exception:
        logger.warning(
            "LLM gap query refinement failed, falling back to template queries",
            exc_info=True,
        )
        return template_fallback_queries(brief)
