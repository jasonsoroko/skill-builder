"""Tests for the DocumenterAgent.

Covers:
- DocumenterAgent conforms to BaseAgent Protocol
- __init__ accepts optional Anthropic client
- run(knowledge_model=dict, brief=SkillBrief) returns SetupDraft
- System prompt instructs prerequisites, API keys, quick start, troubleshooting
- Uses model="claude-sonnet-4-6"
- Uses output_format=SetupDraft via messages.parse
"""

from __future__ import annotations

from unittest.mock import MagicMock

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.production import SetupDraft
from skill_builder.models.synthesis import KnowledgeModel


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


def _make_knowledge_model() -> KnowledgeModel:
    """Create a test KnowledgeModel."""
    return KnowledgeModel(
        canonical_use_cases=["Authenticate API requests", "Cache API responses"],
        required_parameters=["API_KEY: str", "CACHE_TTL: int"],
        common_gotchas=["Keys expire after 30 days"],
        best_practices=["Rotate keys regularly"],
        anti_patterns=["Hardcoding API keys"],
        dependencies=["httpx>=0.27", "redis>=5.0"],
        minimum_viable_example="import httpx\nclient = httpx.Client()\n",
        trigger_phrases=["authenticate with test-tool"],
    )


def _make_fixture_setup_draft() -> SetupDraft:
    """Create a fixture SetupDraft for mock responses."""
    return SetupDraft(
        content="# Setup\n\n## Prerequisites\n\n## Quick Start\n",
        has_prerequisites=True,
        has_quick_start=True,
    )


def _make_mock_response(parsed_output):
    """Create a mock messages.parse response."""
    response = MagicMock()
    response.parsed_output = parsed_output
    response.stop_reason = "end_turn"
    return response


class TestDocumenterAgentProtocol:
    """Test DocumenterAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """DocumenterAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.documenter import DocumenterAgent

        mock_client = MagicMock()
        agent = DocumenterAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)

    def test_init_accepts_optional_client(self) -> None:
        """DocumenterAgent.__init__ accepts optional Anthropic client."""
        from skill_builder.agents.documenter import DocumenterAgent

        mock_client = MagicMock()
        agent = DocumenterAgent(client=mock_client)
        assert agent.client is mock_client


class TestDocumenterAgentRun:
    """Test DocumenterAgent.run() behavior."""

    def test_returns_setup_draft(self) -> None:
        """run() returns SetupDraft."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        result = agent.run(knowledge_model=km.model_dump(), brief=brief)

        assert isinstance(result, SetupDraft)

    def test_uses_sonnet_model(self) -> None:
        """DocumenterAgent uses claude-sonnet-4-6."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"

    def test_uses_setup_draft_output_format(self) -> None:
        """DocumenterAgent passes output_format=SetupDraft."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("output_format") is SetupDraft

    def test_system_prompt_instructs_prerequisites(self) -> None:
        """System prompt mentions prerequisites."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "prerequisite" in system.lower()

    def test_system_prompt_instructs_api_keys(self) -> None:
        """System prompt mentions API keys/env vars."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "api key" in system.lower() or "env" in system.lower()

    def test_system_prompt_instructs_quick_start(self) -> None:
        """System prompt mentions quick start."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "quick start" in system.lower()

    def test_system_prompt_instructs_troubleshooting(self) -> None:
        """System prompt mentions troubleshooting tips."""
        from skill_builder.agents.documenter import DocumenterAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_setup_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = DocumenterAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "troubleshoot" in system.lower()
