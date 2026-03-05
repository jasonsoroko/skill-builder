"""Tests for the ValidatorAgent.

Covers:
- ValidatorAgent conforms to BaseAgent Protocol
- run() receives skill_draft, setup_draft, knowledge_model, brief, categorized_research, iteration
- Heuristics run first; if compactness or syntax fails, returns EvaluationResult with
  overall_pass=False and only heuristic dimensions (LLM evals NOT called)
- When heuristics pass, all 3 LLM evaluators run (mock asyncio.gather call)
- Returns EvaluationResult with all 5 dimensions when everything runs
- overall_pass = all(d.passed for d in dimensions)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.evaluation import EvaluationDimension, EvaluationResult


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


def _make_passing_heuristic(name: str) -> EvaluationDimension:
    """Create a passing heuristic EvaluationDimension."""
    return EvaluationDimension(
        name=name, score=10, feedback="OK", passed=True
    )


def _make_failing_heuristic(name: str) -> EvaluationDimension:
    """Create a failing heuristic EvaluationDimension."""
    return EvaluationDimension(
        name=name, score=3, feedback="Failed", passed=False
    )


def _make_llm_dimension(name: str, score: int = 8) -> EvaluationDimension:
    """Create an LLM evaluator EvaluationDimension."""
    return EvaluationDimension(
        name=name, score=score, feedback="Good", passed=score >= 7
    )


# Fixture data for kwargs
_SKILL_DRAFT = {
    "content": "---\nname: test\n---\n# Test\nimport os\n",
    "line_count": 5,
    "has_frontmatter": True,
    "reference_files": None,
}

_SETUP_DRAFT = {
    "content": "# Setup\nInstall with pip.",
    "has_prerequisites": True,
    "has_quick_start": True,
}

_KNOWLEDGE_MODEL = {
    "canonical_use_cases": ["Use case 1"],
    "required_parameters": ["API_KEY"],
    "common_gotchas": ["Watch out for rate limits"],
    "best_practices": ["Use retry logic"],
    "anti_patterns": ["Hardcoded keys"],
    "dependencies": ["httpx>=0.27"],
    "minimum_viable_example": "import httpx",
    "trigger_phrases": ["use test-tool"],
}

_CATEGORIZED_RESEARCH = {
    "categories": [],
    "source_count": 0,
}


class TestValidatorAgentProtocol:
    """Test ValidatorAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """ValidatorAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.validator import ValidatorAgent

        mock_client = MagicMock()
        agent = ValidatorAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)

    def test_init_accepts_optional_client(self) -> None:
        """ValidatorAgent.__init__ accepts optional Anthropic client."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_client = MagicMock()
        agent = ValidatorAgent(client=mock_client)
        assert agent.client is mock_client


class TestValidatorFailFast:
    """Test heuristic fail-fast behavior (LLM evals skipped on heuristic failure)."""

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_compactness_fails_skips_llm_evals(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """When compactness fails, LLM evaluators are NOT called."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_failing_heuristic("compactness")
        mock_syntax.return_value = _make_passing_heuristic("syntax")

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        assert isinstance(result, EvaluationResult)
        assert result.overall_pass is False
        # Only heuristic dimensions returned
        assert len(result.dimensions) == 2
        # LLM evals never called
        mock_api.assert_not_called()
        mock_comp.assert_not_called()
        mock_tq.assert_not_called()

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_syntax_fails_skips_llm_evals(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """When syntax fails, LLM evaluators are NOT called."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_passing_heuristic("compactness")
        mock_syntax.return_value = _make_failing_heuristic("syntax")

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        assert isinstance(result, EvaluationResult)
        assert result.overall_pass is False
        assert len(result.dimensions) == 2
        mock_api.assert_not_called()
        mock_comp.assert_not_called()
        mock_tq.assert_not_called()

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_both_heuristics_fail_skips_llm_evals(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """When both heuristics fail, LLM evaluators are NOT called."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_failing_heuristic("compactness")
        mock_syntax.return_value = _make_failing_heuristic("syntax")

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        assert result.overall_pass is False
        assert len(result.dimensions) == 2
        mock_api.assert_not_called()

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_fail_fast_returns_correct_iteration(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """Fail-fast result preserves the iteration number."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_failing_heuristic("compactness")
        mock_syntax.return_value = _make_passing_heuristic("syntax")

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            iteration=2,
        )

        assert result.iteration == 2


class TestValidatorHappyPath:
    """Test ValidatorAgent when all evaluators pass."""

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_all_pass_returns_five_dimensions(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """When all 5 evaluators pass, result has 5 dimensions."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_passing_heuristic("compactness")
        mock_syntax.return_value = _make_passing_heuristic("syntax")
        mock_api.return_value = _make_llm_dimension("api_accuracy", 9)
        mock_comp.return_value = _make_llm_dimension("completeness", 8)
        mock_tq.return_value = _make_llm_dimension("trigger_quality", 8)

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        assert isinstance(result, EvaluationResult)
        assert len(result.dimensions) == 5
        assert result.overall_pass is True
        assert result.iteration == 1

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_llm_eval_fails_overall_false(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """When an LLM evaluator fails, overall_pass is False."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_passing_heuristic("compactness")
        mock_syntax.return_value = _make_passing_heuristic("syntax")
        mock_api.return_value = _make_llm_dimension("api_accuracy", 5)  # fails
        mock_comp.return_value = _make_llm_dimension("completeness", 8)
        mock_tq.return_value = _make_llm_dimension("trigger_quality", 8)

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        assert result.overall_pass is False
        assert len(result.dimensions) == 5

    @patch("skill_builder.agents.validator.check_compactness")
    @patch("skill_builder.agents.validator.check_syntax")
    @patch("skill_builder.agents.validator.evaluate_api_accuracy")
    @patch("skill_builder.agents.validator.evaluate_completeness")
    @patch("skill_builder.agents.validator.evaluate_trigger_quality")
    def test_overall_pass_is_all_dimensions_passed(
        self,
        mock_tq,
        mock_comp,
        mock_api,
        mock_syntax,
        mock_compact,
    ) -> None:
        """overall_pass = all(d.passed for d in dimensions)."""
        from skill_builder.agents.validator import ValidatorAgent

        mock_compact.return_value = _make_passing_heuristic("compactness")
        mock_syntax.return_value = _make_passing_heuristic("syntax")
        mock_api.return_value = _make_llm_dimension("api_accuracy", 9)
        mock_comp.return_value = _make_llm_dimension("completeness", 9)
        mock_tq.return_value = _make_llm_dimension("trigger_quality", 9)

        agent = ValidatorAgent(client=MagicMock())
        result = agent.run(
            skill_draft=_SKILL_DRAFT,
            setup_draft=_SETUP_DRAFT,
            knowledge_model=_KNOWLEDGE_MODEL,
            brief=_make_brief(),
            categorized_research=_CATEGORIZED_RESEARCH,
            iteration=1,
        )

        # Verify overall_pass matches all dimensions
        expected = all(d.passed for d in result.dimensions)
        assert result.overall_pass == expected
