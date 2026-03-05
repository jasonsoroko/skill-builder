"""Tests for the heuristic and LLM evaluators.

Covers:
- check_compactness returns EvaluationDimension with passed=True for short content
- check_compactness returns passed=False for 600-line content with score < 10
- check_compactness feedback includes line count
- check_syntax with valid Python block returns passed=True
- check_syntax with invalid Python returns passed=False with error details
- check_syntax ignores bash/json/yaml blocks (only validates ```python blocks)
- check_syntax with no Python blocks returns passed=True with "No Python code blocks found"
- evaluate_api_accuracy is async, accepts (client, skill_content, organized_research),
  returns EvaluationDimension with name="api_accuracy"
- evaluate_api_accuracy calls client.messages.parse with model="claude-opus-4-6"
- evaluate_api_accuracy overrides passed = score >= 7
- evaluate_completeness is async, returns EvaluationDimension with name="completeness"
- evaluate_trigger_quality is async, returns EvaluationDimension with name="trigger_quality"
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from skill_builder.models.evaluation import EvaluationDimension


class TestCheckCompactness:
    """Test compactness evaluator."""

    def test_short_content_passes(self) -> None:
        """Short content under 500 lines returns passed=True."""
        from skill_builder.evaluators.compactness import check_compactness

        result = check_compactness("short content\nline 2\nline 3")
        assert isinstance(result, EvaluationDimension)
        assert result.name == "compactness"
        assert result.passed is True
        assert result.score == 10

    def test_over_500_lines_fails(self) -> None:
        """Content over 500 lines returns passed=False with score < 10."""
        from skill_builder.evaluators.compactness import check_compactness

        content = "\n".join([f"line {i}" for i in range(600)])
        result = check_compactness(content)
        assert isinstance(result, EvaluationDimension)
        assert result.name == "compactness"
        assert result.passed is False
        assert result.score < 10

    def test_exactly_500_lines_passes(self) -> None:
        """Content with exactly 500 lines returns passed=True."""
        from skill_builder.evaluators.compactness import check_compactness

        content = "\n".join([f"line {i}" for i in range(500)])
        result = check_compactness(content)
        assert result.passed is True

    def test_feedback_includes_line_count(self) -> None:
        """Feedback includes the line count."""
        from skill_builder.evaluators.compactness import check_compactness

        content = "\n".join([f"line {i}" for i in range(250)])
        result = check_compactness(content)
        assert "250" in result.feedback

    def test_over_limit_feedback_mentions_exceeds(self) -> None:
        """Feedback for over-limit content mentions exceeding the limit."""
        from skill_builder.evaluators.compactness import check_compactness

        content = "\n".join([f"line {i}" for i in range(600)])
        result = check_compactness(content)
        assert "exceed" in result.feedback.lower() or "500" in result.feedback


class TestCheckSyntax:
    """Test syntax evaluator."""

    def test_valid_python_passes(self) -> None:
        """Valid Python code block returns passed=True."""
        from skill_builder.evaluators.syntax import check_syntax

        content = '```python\nimport os\nprint(os.getcwd())\n```'
        result = check_syntax(content)
        assert isinstance(result, EvaluationDimension)
        assert result.name == "syntax"
        assert result.passed is True
        assert result.score == 10

    def test_invalid_python_fails(self) -> None:
        """Invalid Python code block returns passed=False with error details."""
        from skill_builder.evaluators.syntax import check_syntax

        content = '```python\ndef foo(\n```'
        result = check_syntax(content)
        assert isinstance(result, EvaluationDimension)
        assert result.name == "syntax"
        assert result.passed is False
        assert result.score < 10
        # Error details should be in feedback
        assert len(result.feedback) > 0

    def test_ignores_bash_blocks(self) -> None:
        """Bash code blocks are ignored (only python blocks validated)."""
        from skill_builder.evaluators.syntax import check_syntax

        content = '```bash\necho "hello"\n```'
        result = check_syntax(content)
        assert result.passed is True
        assert "No Python code blocks found" in result.feedback

    def test_ignores_json_blocks(self) -> None:
        """JSON code blocks are ignored."""
        from skill_builder.evaluators.syntax import check_syntax

        content = '```json\n{"key": "value"}\n```'
        result = check_syntax(content)
        assert result.passed is True
        assert "No Python code blocks found" in result.feedback

    def test_ignores_yaml_blocks(self) -> None:
        """YAML code blocks are ignored."""
        from skill_builder.evaluators.syntax import check_syntax

        content = '```yaml\nkey: value\n```'
        result = check_syntax(content)
        assert result.passed is True
        assert "No Python code blocks found" in result.feedback

    def test_no_python_blocks_passes(self) -> None:
        """No Python code blocks returns passed=True with descriptive feedback."""
        from skill_builder.evaluators.syntax import check_syntax

        content = "# Just markdown\n\nSome text without code blocks."
        result = check_syntax(content)
        assert result.passed is True
        assert result.feedback == "No Python code blocks found"

    def test_multiple_blocks_mixed_validity(self) -> None:
        """Multiple Python blocks where some are invalid."""
        from skill_builder.evaluators.syntax import check_syntax

        content = (
            '```python\nimport os\n```\n\n'
            '```python\ndef foo(\n```\n\n'
            '```python\nx = 1\n```'
        )
        result = check_syntax(content)
        assert result.passed is False
        # Should report error for block 2
        assert "Block 2" in result.feedback or "block 2" in result.feedback.lower()

    def test_mixed_language_blocks(self) -> None:
        """Mixed language blocks: only Python blocks are validated."""
        from skill_builder.evaluators.syntax import check_syntax

        content = (
            '```bash\necho "hello"\n```\n\n'
            '```python\nimport os\nprint(os.getcwd())\n```\n\n'
            '```json\n{"key": "value"}\n```'
        )
        result = check_syntax(content)
        assert result.passed is True
        assert "1" in result.feedback  # Reports 1 valid block


# --- LLM Evaluator Tests ---


def _make_mock_client_with_dimension(dim: EvaluationDimension) -> MagicMock:
    """Create a mock Anthropic client that returns a dimension from messages.parse."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed_output = dim
    mock_client.messages.parse.return_value = mock_response
    return mock_client


class TestEvaluateApiAccuracy:
    """Test the API accuracy LLM evaluator."""

    def test_is_async_function(self) -> None:
        """evaluate_api_accuracy is an async function."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        assert asyncio.iscoroutinefunction(evaluate_api_accuracy)

    def test_returns_evaluation_dimension(self) -> None:
        """evaluate_api_accuracy returns EvaluationDimension with name='api_accuracy'."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        dim = EvaluationDimension(
            name="api_accuracy", score=9, feedback="All APIs correct", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_api_accuracy(mock_client, "skill content", {"research": "data"})
        )

        assert isinstance(result, EvaluationDimension)
        assert result.name == "api_accuracy"

    def test_calls_opus_model(self) -> None:
        """evaluate_api_accuracy calls client.messages.parse with model='claude-opus-4-6'."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        dim = EvaluationDimension(
            name="api_accuracy", score=9, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_api_accuracy(mock_client, "skill content", {"research": "data"})
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"
        assert call_kwargs["output_format"] is EvaluationDimension

    def test_passed_override_score_gte_7(self) -> None:
        """evaluate_api_accuracy overrides passed = score >= 7 (score 7 passes)."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        # LLM returns passed=False with score 7 (should be overridden to True)
        dim = EvaluationDimension(
            name="api_accuracy", score=7, feedback="OK", passed=False
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_api_accuracy(mock_client, "skill content", {"research": "data"})
        )

        assert result.passed is True  # Override: 7 >= 7

    def test_passed_override_score_lt_7(self) -> None:
        """evaluate_api_accuracy overrides passed = score >= 7 (score 6 fails)."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        # LLM returns passed=True with score 6 (should be overridden to False)
        dim = EvaluationDimension(
            name="api_accuracy", score=6, feedback="Issues", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_api_accuracy(mock_client, "skill content", {"research": "data"})
        )

        assert result.passed is False  # Override: 6 < 7

    def test_prompt_includes_skill_content_and_research(self) -> None:
        """Prompt includes skill content and organized research."""
        from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy

        dim = EvaluationDimension(
            name="api_accuracy", score=9, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_api_accuracy(
                mock_client, "my skill content here", {"endpoint": "/api/v1"}
            )
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        messages = call_kwargs["messages"]
        prompt_text = str(messages)
        assert "my skill content here" in prompt_text
        assert "/api/v1" in prompt_text


class TestEvaluateCompleteness:
    """Test the completeness LLM evaluator."""

    def test_is_async_function(self) -> None:
        """evaluate_completeness is an async function."""
        from skill_builder.evaluators.completeness import evaluate_completeness

        assert asyncio.iscoroutinefunction(evaluate_completeness)

    def test_returns_evaluation_dimension(self) -> None:
        """evaluate_completeness returns EvaluationDimension with name='completeness'."""
        from skill_builder.evaluators.completeness import evaluate_completeness

        dim = EvaluationDimension(
            name="completeness", score=8, feedback="Complete", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_completeness(mock_client, "skill content", {"use_cases": []})
        )

        assert isinstance(result, EvaluationDimension)
        assert result.name == "completeness"

    def test_passed_override(self) -> None:
        """evaluate_completeness overrides passed = score >= 7."""
        from skill_builder.evaluators.completeness import evaluate_completeness

        dim = EvaluationDimension(
            name="completeness", score=5, feedback="Missing", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_completeness(mock_client, "skill content", {"use_cases": []})
        )

        assert result.passed is False  # Override: 5 < 7

    def test_calls_opus_model(self) -> None:
        """evaluate_completeness calls client.messages.parse with model='claude-opus-4-6'."""
        from skill_builder.evaluators.completeness import evaluate_completeness

        dim = EvaluationDimension(
            name="completeness", score=8, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_completeness(mock_client, "skill content", {"use_cases": []})
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_prompt_includes_knowledge_model(self) -> None:
        """Prompt includes knowledge model data."""
        from skill_builder.evaluators.completeness import evaluate_completeness

        dim = EvaluationDimension(
            name="completeness", score=8, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_completeness(
                mock_client,
                "my skill",
                {"canonical_use_cases": ["auth flow"]},
            )
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        prompt_text = str(call_kwargs["messages"])
        assert "auth flow" in prompt_text


class TestEvaluateTriggerQuality:
    """Test the trigger quality LLM evaluator."""

    def test_is_async_function(self) -> None:
        """evaluate_trigger_quality is an async function."""
        from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality

        assert asyncio.iscoroutinefunction(evaluate_trigger_quality)

    def test_returns_evaluation_dimension(self) -> None:
        """evaluate_trigger_quality returns EvaluationDimension with name='trigger_quality'."""
        from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality

        dim = EvaluationDimension(
            name="trigger_quality", score=8, feedback="Good trigger", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_trigger_quality(mock_client, "skill content", {"phrases": []})
        )

        assert isinstance(result, EvaluationDimension)
        assert result.name == "trigger_quality"

    def test_passed_override(self) -> None:
        """evaluate_trigger_quality overrides passed = score >= 7."""
        from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality

        dim = EvaluationDimension(
            name="trigger_quality", score=6, feedback="Vague trigger", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        result = asyncio.run(
            evaluate_trigger_quality(mock_client, "skill content", {"phrases": []})
        )

        assert result.passed is False  # Override: 6 < 7

    def test_calls_opus_model(self) -> None:
        """evaluate_trigger_quality calls client.messages.parse with model='claude-opus-4-6'."""
        from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality

        dim = EvaluationDimension(
            name="trigger_quality", score=8, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_trigger_quality(mock_client, "skill content", {"phrases": []})
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_prompt_includes_trigger_phrases(self) -> None:
        """Prompt includes trigger phrases from knowledge model."""
        from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality

        dim = EvaluationDimension(
            name="trigger_quality", score=8, feedback="OK", passed=True
        )
        mock_client = _make_mock_client_with_dimension(dim)

        asyncio.run(
            evaluate_trigger_quality(
                mock_client,
                "my skill",
                {"trigger_phrases": ["use my-tool for auth"]},
            )
        )

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        prompt_text = str(call_kwargs["messages"])
        assert "use my-tool for auth" in prompt_text
