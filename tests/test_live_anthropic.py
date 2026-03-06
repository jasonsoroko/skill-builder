"""Layer 2: Anthropic SDK contract verification.

Proves messages.parse with output_format=PydanticModel works for Sonnet and
Opus with the exact calling conventions used in production agents.
Total cost: ~$0.10. Run with: pytest -m live --tb=short -v
"""

from __future__ import annotations

import os

import pytest

from skill_builder.models.evaluation import EvaluationDimension
from skill_builder.models.synthesis import CategorizedResearch, GapReport

pytestmark = [pytest.mark.live, pytest.mark.timeout(60)]


def _skip_if_no_anthropic() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


class TestAnthropicSDKContract:
    """Verify messages.parse + output_format works for production calling patterns."""

    def test_sonnet_messages_parse(self) -> None:
        """Sonnet + messages.parse + output_format=CategorizedResearch (Organizer pattern)."""
        _skip_if_no_anthropic()
        from anthropic import Anthropic

        client = Anthropic()
        response = client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            output_format=CategorizedResearch,
            system="Organize this text into categories.",
            messages=[{
                "role": "user",
                "content": "Exa is a search API for semantic search. Tavily is a web search API for factual queries.",
            }],
        )
        assert response.parsed_output is not None
        result = response.parsed_output
        assert isinstance(result, CategorizedResearch)
        assert len(result.categories) > 0
        assert response.usage.input_tokens > 0

    def test_opus_adaptive_thinking_messages_parse(self) -> None:
        """Opus + adaptive thinking + output_format=GapReport (GapAnalyzer pattern)."""
        _skip_if_no_anthropic()
        from anthropic import Anthropic

        client = Anthropic()
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_format=GapReport,
            system="Analyze research completeness.",
            messages=[{
                "role": "user",
                "content": (
                    "Required capabilities: semantic search, result filtering.\n"
                    "Research: Exa provides semantic search with neural ranking. "
                    "No information about result filtering was found."
                ),
            }],
        )
        assert response.parsed_output is not None
        result = response.parsed_output
        assert isinstance(result, GapReport)
        assert isinstance(result.is_sufficient, bool)
        assert response.usage.input_tokens > 0

    def test_opus_messages_parse_evaluation_dimension(self) -> None:
        """Opus + output_format=EvaluationDimension (LLM evaluator pattern)."""
        _skip_if_no_anthropic()
        from anthropic import Anthropic

        client = Anthropic()
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=4096,
            output_format=EvaluationDimension,
            system="Evaluate this skill content on api_accuracy. Score 1-10.",
            messages=[{
                "role": "user",
                "content": (
                    "Skill content: Use exa.search('query', num_results=10) for semantic search. "
                    "Use tavily.search('query', max_results=5) for web search."
                ),
            }],
        )
        assert response.parsed_output is not None
        result = response.parsed_output
        assert isinstance(result, EvaluationDimension)
        assert 1 <= result.score <= 10
        assert isinstance(result.passed, bool)
