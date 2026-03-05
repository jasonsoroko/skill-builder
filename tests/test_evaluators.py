"""Tests for the heuristic evaluators.

Covers:
- check_compactness returns EvaluationDimension with passed=True for short content
- check_compactness returns passed=False for 600-line content with score < 10
- check_compactness feedback includes line count
- check_syntax with valid Python block returns passed=True
- check_syntax with invalid Python returns passed=False with error details
- check_syntax ignores bash/json/yaml blocks (only validates ```python blocks)
- check_syntax with no Python blocks returns passed=True with "No Python code blocks found"
"""

from __future__ import annotations

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
