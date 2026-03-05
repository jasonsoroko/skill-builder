"""Tests for the LearnerAgent.

Covers:
- LearnerAgent conforms to BaseAgent Protocol
- run(categorized_research=dict, gap_report=dict, brief=brief) returns KnowledgeModel
- All KnowledgeModel fields are populated
- Uses model="claude-sonnet-4-6"
- Uses output_format=KnowledgeModel via messages.parse
"""

from __future__ import annotations

from unittest.mock import MagicMock

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.synthesis import (
    CategorizedResearch,
    ContentItem,
    GapReport,
    KnowledgeModel,
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
        "required_capabilities": ["auth", "caching"],
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
    )


def _make_gap_report() -> GapReport:
    """Create a test GapReport."""
    return GapReport(
        is_sufficient=True,
        identified_gaps=[],
        recommended_search_queries=[],
    )


def _make_fixture_knowledge_model() -> KnowledgeModel:
    """Create a fixture KnowledgeModel for mock responses."""
    return KnowledgeModel(
        canonical_use_cases=["Authenticate API requests", "Cache API responses"],
        required_parameters=["API_KEY: str", "CACHE_TTL: int"],
        common_gotchas=["Keys expire after 30 days"],
        best_practices=["Rotate keys regularly", "Use Redis for caching"],
        anti_patterns=["Hardcoding API keys", "Unbounded cache growth"],
        dependencies=["httpx>=0.27", "redis>=5.0"],
        minimum_viable_example=(
            "import httpx\n"
            "client = httpx.Client(headers={'Authorization': 'Bearer KEY'})\n"
            "resp = client.get('https://api.test.dev/data')\n"
        ),
        trigger_phrases=["authenticate with test-tool", "cache test-tool responses"],
    )


def _make_mock_response(parsed_output):
    """Create a mock messages.parse response."""
    response = MagicMock()
    response.parsed_output = parsed_output
    response.stop_reason = "end_turn"
    return response


class TestLearnerAgentProtocol:
    """Test LearnerAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """LearnerAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.learner import LearnerAgent

        mock_client = MagicMock()
        agent = LearnerAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)


class TestLearnerAgentRun:
    """Test LearnerAgent.run() behavior."""

    def test_returns_knowledge_model(self) -> None:
        """run() returns KnowledgeModel with all fields populated."""
        from skill_builder.agents.learner import LearnerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        gap_report = _make_gap_report()
        fixture = _make_fixture_knowledge_model()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = LearnerAgent(client=mock_client)
        result = agent.run(
            categorized_research=categorized.model_dump(),
            gap_report=gap_report.model_dump(),
            brief=brief,
        )

        assert isinstance(result, KnowledgeModel)

    def test_all_knowledge_model_fields_populated(self) -> None:
        """All KnowledgeModel fields have values."""
        from skill_builder.agents.learner import LearnerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        gap_report = _make_gap_report()
        fixture = _make_fixture_knowledge_model()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = LearnerAgent(client=mock_client)
        result = agent.run(
            categorized_research=categorized.model_dump(),
            gap_report=gap_report.model_dump(),
            brief=brief,
        )

        assert len(result.canonical_use_cases) > 0
        assert len(result.required_parameters) > 0
        assert len(result.common_gotchas) > 0
        assert len(result.best_practices) > 0
        assert len(result.anti_patterns) > 0
        assert len(result.dependencies) > 0
        assert len(result.minimum_viable_example) > 0
        assert len(result.trigger_phrases) > 0

    def test_uses_sonnet_model(self) -> None:
        """LearnerAgent uses claude-sonnet-4-6."""
        from skill_builder.agents.learner import LearnerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        gap_report = _make_gap_report()
        fixture = _make_fixture_knowledge_model()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = LearnerAgent(client=mock_client)
        agent.run(
            categorized_research=categorized.model_dump(),
            gap_report=gap_report.model_dump(),
            brief=brief,
        )

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"

    def test_uses_knowledge_model_output_format(self) -> None:
        """LearnerAgent passes output_format=KnowledgeModel."""
        from skill_builder.agents.learner import LearnerAgent

        brief = _make_brief()
        categorized = _make_categorized_research()
        gap_report = _make_gap_report()
        fixture = _make_fixture_knowledge_model()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = LearnerAgent(client=mock_client)
        agent.run(
            categorized_research=categorized.model_dump(),
            gap_report=gap_report.model_dump(),
            brief=brief,
        )

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("output_format") is KnowledgeModel
