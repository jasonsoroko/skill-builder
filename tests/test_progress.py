"""Tests for PipelineProgress Rich CLI display.

Covers:
- Initialization with verbose flag
- phase_start / phase_complete state tracking
- eval_score formatting: "9/10 PASS" or "4/10 FAIL"
- budget_display formatting: "$5.82 / $25.00 (23.3%)"
- summary_panel accepts all required parameters
- Non-TTY fallback: plain text output when not a terminal
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from skill_builder.progress import PipelineProgress


class TestInitialization:
    """PipelineProgress initialization."""

    def test_accepts_verbose_bool(self) -> None:
        """PipelineProgress.__init__ accepts verbose bool."""
        progress = PipelineProgress(verbose=True)
        assert progress.verbose is True

    def test_defaults_verbose_false(self) -> None:
        """PipelineProgress defaults verbose to False."""
        progress = PipelineProgress()
        assert progress.verbose is False


class TestPhaseTracking:
    """phase_start and phase_complete record state."""

    def test_phase_start_records_state(self) -> None:
        """phase_start(phase, agent) records phase and agent."""
        progress = PipelineProgress(verbose=False)
        progress.phase_start("harvesting", "harvest")
        assert progress._phase == "harvesting"
        assert progress._agent == "harvest"

    def test_phase_complete_records_state(self) -> None:
        """phase_complete(phase, elapsed) records elapsed time."""
        progress = PipelineProgress(verbose=False)
        progress.phase_complete("harvesting", 2.5)
        # Should not raise -- method accepts phase and elapsed


class TestEvalScore:
    """eval_score formatting."""

    def test_eval_score_pass_format(self) -> None:
        """eval_score formats passing score as '9/10 PASS'."""
        progress = PipelineProgress(verbose=False)
        output = StringIO()
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            # Capture what gets printed
            printed = []
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.eval_score("api_accuracy", 9, True)
        assert any("9/10" in s and "PASS" in s for s in printed)

    def test_eval_score_fail_format(self) -> None:
        """eval_score formats failing score as '4/10 FAIL'."""
        progress = PipelineProgress(verbose=False)
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            printed = []
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.eval_score("api_accuracy", 4, False)
        assert any("4/10" in s and "FAIL" in s for s in printed)


class TestBudgetDisplay:
    """budget_display formatting."""

    def test_budget_display_format(self) -> None:
        """budget_display formats as '$5.82 / $25.00 (23.3%)'."""
        progress = PipelineProgress(verbose=True)
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            printed = []
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.budget_display(5.82, 25.0)
        joined = " ".join(printed)
        assert "$5.82" in joined
        assert "$25.00" in joined
        assert "23.3%" in joined


class TestSummaryPanel:
    """summary_panel accepts all required parameters."""

    def test_summary_panel_accepts_all_params(self) -> None:
        """summary_panel accepts total_time, total_cost, eval_dimensions, etc."""
        progress = PipelineProgress(verbose=False)
        eval_dims = [
            {"name": "api_accuracy", "score": 9, "passed": True, "feedback": "Good"},
            {"name": "completeness", "score": 8, "passed": True, "feedback": "OK"},
        ]
        # Should not raise
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            mock_console.print = lambda *args, **kwargs: None
            progress.summary_panel(
                total_time=42.5,
                total_cost=3.14,
                eval_dimensions=eval_dims,
                gap_loops=1,
                validation_loops=0,
                output_path="/tmp/output/test-skill",
                verification_instructions="Test the skill by asking Claude.",
            )

    def test_summary_panel_includes_all_fields(self) -> None:
        """summary_panel output includes time, cost, scores, path, instructions."""
        progress = PipelineProgress(verbose=False)
        eval_dims = [
            {"name": "api_accuracy", "score": 9, "passed": True, "feedback": "Good"},
        ]
        printed = []
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.summary_panel(
                total_time=42.5,
                total_cost=3.14,
                eval_dimensions=eval_dims,
                gap_loops=1,
                validation_loops=0,
                output_path="/tmp/output/test-skill",
                verification_instructions="Test the skill by asking Claude.",
            )
        joined = " ".join(printed)
        assert "42.5" in joined or "42.5s" in joined
        assert "3.14" in joined
        assert "api_accuracy" in joined
        assert "/tmp/output/test-skill" in joined


class TestNonTTYFallback:
    """Non-TTY environments get plain text output."""

    def test_phase_start_plain_text(self) -> None:
        """When not a TTY, phase_start outputs plain text."""
        progress = PipelineProgress(verbose=False)
        printed = []
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.phase_start("harvesting", "harvest")
        # Should have printed a plain text line
        assert len(printed) >= 1
        joined = " ".join(printed)
        assert "harvesting" in joined.lower()

    def test_phase_complete_plain_text(self) -> None:
        """When not a TTY, phase_complete outputs plain text."""
        progress = PipelineProgress(verbose=False)
        printed = []
        with patch.object(progress, "_console") as mock_console:
            mock_console.is_terminal = False
            mock_console.print = lambda *args, **kwargs: printed.append(str(args[0]))
            progress.phase_complete("harvesting", 2.5)
        assert len(printed) >= 1
        joined = " ".join(printed)
        assert "harvesting" in joined.lower()
        assert "2.5" in joined
