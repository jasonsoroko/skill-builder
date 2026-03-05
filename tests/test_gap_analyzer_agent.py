"""Tests for the GapAnalyzerAgent.

Covers:
- GapAnalyzerAgent conforms to BaseAgent Protocol
- Sufficient case: is_sufficient=True, empty gaps
- Insufficient case: is_sufficient=False with gaps and search queries
- Every required_capability from brief appears in the prompt (SYNTH-04)
- Uses model="claude-opus-4-6" and thinking={"type": "adaptive"}
- Harvest warnings included in prompt when present
- stop_reason="max_tokens" logs a warning
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.synthesis import (
    CategorizedResearch,
    ContentItem,
    GapReport,
    ResearchCategory,
)


def _make_brief(**overrides) -> SkillBrief:
    """Create a test SkillBrief."""
    defaults = {
        "name": "test-tool",
        "description": "A test tool for research",
        "seed_urls": [SeedUrl(url="https://docs.test.dev/", type="docs")],
        "tool_category": "testing",
        "scope": "Testing the tool",
        "required_capabilities": ["auth", "caching", "logging"],
        "deploy_target": "user",
    }
    defaults.update(overrides)
    return SkillBrief(**defaults)


def _make_categorized_research() -> CategorizedResearch:
    """Create a test CategorizedResearch."""
    return CategorizedResearch(
        categories=[
            ResearchCategory(
                name="authentication",
                content=[
                    ContentItem(
                        text="API key authentication",
                        source_url="https://docs.test.dev/auth",
                    ),
                ],
            ),
        ],
        source_count=1,
        tools_covered=["test-tool"],
    )


def _make_mock_response(parsed_output, stop_reason="end_turn"):
    """Create a mock messages.parse response."""
    response = MagicMock()
    response.parsed_output = parsed_output
    response.stop_reason = stop_reason
    return response


class TestGapAnalyzerProtocol:
    """Test GapAnalyzerAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """GapAnalyzerAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        mock_client = MagicMock()
        agent = GapAnalyzerAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)


class TestGapAnalyzerSufficient:
    """Test sufficient case."""

    def test_returns_sufficient_gap_report(self) -> None:
        """When research is sufficient, returns is_sufficient=True."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(
            is_sufficient=True,
            identified_gaps=[],
            recommended_search_queries=[],
        )

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        result = agent.run(
            categorized_research=categorized.model_dump(),
            brief=brief,
        )

        assert isinstance(result, GapReport)
        assert result.is_sufficient is True
        assert result.identified_gaps == []


class TestGapAnalyzerInsufficient:
    """Test insufficient case."""

    def test_returns_insufficient_with_gaps(self) -> None:
        """When research has gaps, returns is_sufficient=False with details."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(
            is_sufficient=False,
            identified_gaps=["Missing caching documentation", "No logging examples"],
            recommended_search_queries=["test-tool caching guide", "test-tool logging setup"],
        )

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        result = agent.run(
            categorized_research=categorized.model_dump(),
            brief=brief,
        )

        assert isinstance(result, GapReport)
        assert result.is_sufficient is False
        assert len(result.identified_gaps) == 2
        assert len(result.recommended_search_queries) == 2


class TestGapAnalyzerPrompt:
    """Test prompt construction."""

    def test_every_required_capability_in_prompt(self) -> None:
        """SYNTH-04: Every required_capability from brief appears in the prompt."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        capabilities = ["auth", "caching", "logging", "rate-limiting", "error-handling"]
        brief = _make_brief(required_capabilities=capabilities)
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        agent.run(categorized_research=categorized.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)

        for cap in capabilities:
            assert cap in prompt_text, f"Required capability '{cap}' missing from prompt"

    def test_harvest_warnings_included_when_present(self) -> None:
        """Harvest warnings appear in the prompt when passed."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)
        warnings = ["Version conflict: v1.5 vs v2.0", "Saturation: missing caching"]

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        agent.run(
            categorized_research=categorized.model_dump(),
            brief=brief,
            harvest_warnings=warnings,
        )

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)

        assert "Version conflict" in prompt_text
        assert "Saturation: missing caching" in prompt_text


class TestGapAnalyzerModelConfig:
    """Test model and thinking configuration."""

    def test_uses_opus_model(self) -> None:
        """GapAnalyzerAgent uses claude-opus-4-6."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        agent.run(categorized_research=categorized.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("model") == "claude-opus-4-6"

    def test_uses_adaptive_thinking(self) -> None:
        """GapAnalyzerAgent uses thinking={"type": "adaptive"}."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        agent.run(categorized_research=categorized.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("thinking") == {"type": "adaptive"}

    def test_uses_gap_report_output_format(self) -> None:
        """GapAnalyzerAgent passes output_format=GapReport."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = GapAnalyzerAgent(client=mock_client)
        agent.run(categorized_research=categorized.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("output_format") is GapReport


class TestGapAnalyzerMaxTokensWarning:
    """Test stop_reason handling."""

    def test_max_tokens_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """When stop_reason is 'max_tokens', a warning is logged."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        fixture = GapReport(is_sufficient=True)

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(
            fixture, stop_reason="max_tokens"
        )

        agent = GapAnalyzerAgent(client=mock_client)
        with caplog.at_level(logging.WARNING, logger="skill_builder.agents.gap_analyzer"):
            result = agent.run(
                categorized_research=categorized.model_dump(), brief=brief
            )

        assert result is not None
        assert any("max_tokens" in record.message for record in caplog.records)
