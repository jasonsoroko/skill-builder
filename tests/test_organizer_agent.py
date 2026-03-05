"""Tests for the OrganizerAgent.

Covers:
- OrganizerAgent conforms to BaseAgent Protocol
- run(raw_harvest=dict, brief=SkillBrief) returns CategorizedResearch
- Prompt includes required_capabilities and page content
- Uses model="claude-sonnet-4-6"
- Uses output_format=CategorizedResearch via messages.parse
- Harvest warnings included in prompt when present
"""

from __future__ import annotations

from unittest.mock import MagicMock

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.harvest import HarvestPage, HarvestResult
from skill_builder.models.synthesis import (
    CategorizedResearch,
    ContentItem,
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


def _make_harvest_result(**overrides) -> HarvestResult:
    """Create a test HarvestResult and return its dict form."""
    pages = [
        HarvestPage(
            url="https://docs.test.dev/intro",
            title="Test Tool Intro",
            content="Test tool provides authentication and caching features.",
            source_type="crawl",
        ),
        HarvestPage(
            url="https://docs.test.dev/advanced",
            title="Advanced Usage",
            content="Advanced logging and monitoring capabilities.",
            source_type="crawl",
        ),
    ]
    defaults = {"pages": pages, "total_pages": 2, "warnings": []}
    defaults.update(overrides)
    return HarvestResult(**defaults)


def _make_fixture_categorized_research() -> CategorizedResearch:
    """Create a fixture CategorizedResearch for mock responses."""
    return CategorizedResearch(
        categories=[
            ResearchCategory(
                name="authentication",
                content=[
                    ContentItem(
                        text="Test tool uses API keys for auth",
                        source_url="https://docs.test.dev/intro",
                    ),
                ],
            ),
            ResearchCategory(
                name="caching",
                content=[
                    ContentItem(
                        text="Built-in caching with TTL support",
                        source_url="https://docs.test.dev/intro",
                    ),
                ],
            ),
        ],
        source_count=2,
        tools_covered=["test-tool"],
    )


def _make_mock_response(parsed_output):
    """Create a mock messages.parse response with parsed_output."""
    response = MagicMock()
    response.parsed_output = parsed_output
    response.stop_reason = "end_turn"
    return response


class TestOrganizerAgentProtocol:
    """Test OrganizerAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """OrganizerAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.organizer import OrganizerAgent

        mock_client = MagicMock()
        agent = OrganizerAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)


class TestOrganizerAgentRun:
    """Test OrganizerAgent.run() behavior."""

    def test_returns_categorized_research(self) -> None:
        """run(raw_harvest=dict, brief=brief) returns CategorizedResearch."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief()
        harvest = _make_harvest_result()
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        result = agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        assert isinstance(result, CategorizedResearch)
        assert len(result.categories) == 2
        assert result.source_count == 2

    def test_prompt_includes_required_capabilities(self) -> None:
        """The prompt sent to the LLM includes required_capabilities from brief."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief(required_capabilities=["auth", "caching", "logging"])
        harvest = _make_harvest_result()
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        # Inspect the messages arg passed to messages.parse
        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)

        assert "auth" in prompt_text
        assert "caching" in prompt_text
        assert "logging" in prompt_text

    def test_prompt_includes_page_content(self) -> None:
        """The prompt sent to the LLM includes harvested page content."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief()
        harvest = _make_harvest_result()
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)

        assert "authentication and caching features" in prompt_text
        assert "logging and monitoring capabilities" in prompt_text

    def test_uses_sonnet_model(self) -> None:
        """OrganizerAgent uses claude-sonnet-4-6."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief()
        harvest = _make_harvest_result()
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"

    def test_uses_categorized_research_output_format(self) -> None:
        """OrganizerAgent passes output_format=CategorizedResearch."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief()
        harvest = _make_harvest_result()
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("output_format") is CategorizedResearch

    def test_harvest_warnings_included_in_prompt(self) -> None:
        """Harvest warnings are included in the prompt when present."""
        from skill_builder.agents.organizer import OrganizerAgent

        brief = _make_brief()
        harvest = _make_harvest_result(
            warnings=["Version mismatch: found 1.5, target 2.0", "Missing auth docs"]
        )
        fixture = _make_fixture_categorized_research()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = OrganizerAgent(client=mock_client)
        agent.run(raw_harvest=harvest.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)

        assert "Version mismatch" in prompt_text
        assert "Missing auth docs" in prompt_text
