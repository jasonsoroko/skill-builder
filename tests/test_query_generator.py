"""Tests for the harvest query generator module.

Covers:
- template_fallback_queries produces correct count (one per capability per tool)
- generate_search_queries calls messages.parse (mocked Anthropic client)
- generate_search_queries falls back to templates on LLM error
- refine_gap_queries passes raw queries through LLM
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.synthesis import GeneratedQueries


@pytest.fixture
def sample_brief() -> SkillBrief:
    """Return a SkillBrief fixture for query generation tests."""
    return SkillBrief(
        name="exa-tavily-firecrawl",
        description="Research crawling with Exa, Tavily, and Firecrawl",
        seed_urls=[
            SeedUrl(url="https://docs.exa.ai/", type="docs"),
            SeedUrl(url="https://docs.tavily.com/", type="docs"),
        ],
        tool_category="research",
        scope="Comprehensive research crawling",
        required_capabilities=["semantic search", "web search", "site crawling"],
        deploy_target="user",
    )


class TestTemplateFallbackQueries:
    """Test template-based fallback query generation."""

    def test_produces_one_exa_query_per_capability(self, sample_brief: SkillBrief) -> None:
        """template_fallback_queries produces one Exa query per required_capability."""
        from skill_builder.harvest.query_generator import template_fallback_queries

        result = template_fallback_queries(sample_brief)
        assert len(result.exa_queries) == len(sample_brief.required_capabilities)

    def test_produces_one_tavily_query_per_capability(self, sample_brief: SkillBrief) -> None:
        """template_fallback_queries produces one Tavily query per required_capability."""
        from skill_builder.harvest.query_generator import template_fallback_queries

        result = template_fallback_queries(sample_brief)
        assert len(result.tavily_queries) == len(sample_brief.required_capabilities)

    def test_queries_contain_brief_name(self, sample_brief: SkillBrief) -> None:
        """template_fallback_queries includes brief name in queries."""
        from skill_builder.harvest.query_generator import template_fallback_queries

        result = template_fallback_queries(sample_brief)
        for query in result.exa_queries:
            assert sample_brief.name in query
        for query in result.tavily_queries:
            assert sample_brief.name in query

    def test_queries_contain_capabilities(self, sample_brief: SkillBrief) -> None:
        """template_fallback_queries includes capability names in queries."""
        from skill_builder.harvest.query_generator import template_fallback_queries

        result = template_fallback_queries(sample_brief)
        for i, cap in enumerate(sample_brief.required_capabilities):
            assert cap in result.exa_queries[i]
            assert cap in result.tavily_queries[i]

    def test_returns_generated_queries_type(self, sample_brief: SkillBrief) -> None:
        """template_fallback_queries returns a GeneratedQueries instance."""
        from skill_builder.harvest.query_generator import template_fallback_queries

        result = template_fallback_queries(sample_brief)
        assert isinstance(result, GeneratedQueries)


class TestGenerateSearchQueries:
    """Test LLM-generated search queries."""

    def test_calls_messages_parse(self, sample_brief: SkillBrief) -> None:
        """generate_search_queries calls client.messages.parse with correct parameters."""
        from skill_builder.harvest.query_generator import generate_search_queries

        mock_response = MagicMock()
        mock_response.parsed_output = GeneratedQueries(
            exa_queries=["exa q1", "exa q2", "exa q3"],
            tavily_queries=["tavily q1", "tavily q2", "tavily q3"],
        )
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_response

        result = generate_search_queries(mock_client, sample_brief)

        mock_client.messages.parse.assert_called_once()
        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs.kwargs["output_format"] is GeneratedQueries
        assert isinstance(result, GeneratedQueries)

    def test_falls_back_to_templates_on_llm_error(self, sample_brief: SkillBrief) -> None:
        """generate_search_queries falls back to template_fallback_queries on exception."""
        from skill_builder.harvest.query_generator import generate_search_queries

        mock_client = MagicMock()
        mock_client.messages.parse.side_effect = Exception("LLM connection failed")

        result = generate_search_queries(mock_client, sample_brief)

        assert isinstance(result, GeneratedQueries)
        assert len(result.exa_queries) == len(sample_brief.required_capabilities)
        assert len(result.tavily_queries) == len(sample_brief.required_capabilities)


class TestRefineGapQueries:
    """Test LLM-refined gap closure queries."""

    def test_refine_gap_queries_calls_llm(self, sample_brief: SkillBrief) -> None:
        """refine_gap_queries passes raw queries through LLM."""
        from skill_builder.harvest.query_generator import refine_gap_queries

        mock_response = MagicMock()
        mock_response.parsed_output = GeneratedQueries(
            exa_queries=["refined exa query"],
            tavily_queries=["refined tavily query"],
        )
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_response

        raw_queries = ["firecrawl batch API", "exa rate limits"]
        result = refine_gap_queries(mock_client, sample_brief, raw_queries)

        mock_client.messages.parse.assert_called_once()
        assert isinstance(result, GeneratedQueries)
        assert result.exa_queries == ["refined exa query"]

    def test_refine_gap_queries_falls_back_on_error(self, sample_brief: SkillBrief) -> None:
        """refine_gap_queries returns template queries on LLM failure."""
        from skill_builder.harvest.query_generator import refine_gap_queries

        mock_client = MagicMock()
        mock_client.messages.parse.side_effect = Exception("LLM error")

        raw_queries = ["some query"]
        result = refine_gap_queries(mock_client, sample_brief, raw_queries)

        assert isinstance(result, GeneratedQueries)
        assert len(result.exa_queries) > 0
