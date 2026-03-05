"""Tests for the MapperAgent.

Covers:
- MapperAgent conforms to BaseAgent Protocol
- __init__ accepts optional Anthropic client
- run(knowledge_model=dict, brief=SkillBrief) returns SkillDraft
- System prompt instructs 500-line budget, DO/DON'T section, worked examples, YAML frontmatter with pushy trigger
- When failed_dimensions is provided, prompt includes only failed dimension feedback
- Prompt includes all canonical_use_cases from KnowledgeModel for worked examples
- messages.parse is called with max_tokens=8192
"""

from __future__ import annotations

from unittest.mock import MagicMock

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.production import SkillDraft
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


def _make_fixture_skill_draft() -> SkillDraft:
    """Create a fixture SkillDraft for mock responses."""
    return SkillDraft(
        content="---\nname: test-tool\ndescription: Tests things.\n---\n# Test Tool\n",
        line_count=5,
        has_frontmatter=True,
        reference_files=None,
    )


def _make_mock_response(parsed_output):
    """Create a mock messages.parse response."""
    response = MagicMock()
    response.parsed_output = parsed_output
    response.stop_reason = "end_turn"
    return response


class TestMapperAgentProtocol:
    """Test MapperAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """MapperAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.mapper import MapperAgent

        mock_client = MagicMock()
        agent = MapperAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)

    def test_init_accepts_optional_client(self) -> None:
        """MapperAgent.__init__ accepts optional Anthropic client."""
        from skill_builder.agents.mapper import MapperAgent

        mock_client = MagicMock()
        agent = MapperAgent(client=mock_client)
        assert agent.client is mock_client


class TestMapperAgentRun:
    """Test MapperAgent.run() behavior."""

    def test_returns_skill_draft(self) -> None:
        """run() returns SkillDraft."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        result = agent.run(knowledge_model=km.model_dump(), brief=brief)

        assert isinstance(result, SkillDraft)

    def test_uses_sonnet_model(self) -> None:
        """MapperAgent uses claude-sonnet-4-6."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"

    def test_uses_skill_draft_output_format(self) -> None:
        """MapperAgent passes output_format=SkillDraft."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("output_format") is SkillDraft

    def test_max_tokens_8192(self) -> None:
        """MapperAgent uses max_tokens=8192."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 8192

    def test_system_prompt_instructs_500_line_budget(self) -> None:
        """System prompt mentions 500-line budget."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "500" in system

    def test_system_prompt_instructs_do_dont_section(self) -> None:
        """System prompt instructs DO/DON'T section."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        # Check for DO/DON'T or Important Rules mention
        assert "DO" in system and "DON'T" in system or "DO/" in system

    def test_system_prompt_instructs_worked_examples(self) -> None:
        """System prompt instructs worked examples."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "worked example" in system.lower() or "example" in system.lower()

    def test_system_prompt_instructs_yaml_frontmatter(self) -> None:
        """System prompt instructs YAML frontmatter with pushy trigger."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "frontmatter" in system.lower()

    def test_prompt_includes_canonical_use_cases(self) -> None:
        """Prompt includes all canonical_use_cases from KnowledgeModel."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        prompt_text = str(messages)

        assert "Authenticate API requests" in prompt_text
        assert "Cache API responses" in prompt_text

    def test_failed_dimensions_included_in_prompt(self) -> None:
        """When failed_dimensions is provided, prompt includes fix feedback."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        failed_dims = [
            {"name": "compactness", "feedback": "520 lines (exceeds 500-line limit by 20)"},
        ]

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(
            knowledge_model=km.model_dump(),
            brief=brief,
            failed_dimensions=failed_dims,
        )

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        prompt_text = str(messages)

        assert "compactness" in prompt_text
        assert "520 lines" in prompt_text

    def test_failed_dimensions_not_in_prompt_when_absent(self) -> None:
        """When no failed_dimensions, no fix section in prompt."""
        from skill_builder.agents.mapper import MapperAgent

        brief = _make_brief()
        km = _make_knowledge_model()
        fixture = _make_fixture_skill_draft()

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = _make_mock_response(fixture)

        agent = MapperAgent(client=mock_client)
        agent.run(knowledge_model=km.model_dump(), brief=brief)

        call_kwargs = mock_client.messages.parse.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        prompt_text = str(messages)

        assert "FIX THESE ISSUES" not in prompt_text
