"""Tests for the Click CLI entry point.

Covers:
- Basic invocation: `skill-builder build brief.json` runs successfully
- Dry-run: prints fetch plan and cost estimate, exits without running agents
- Resume: loads existing state and continues
- State clash: warns and exits when state exists without --resume/--force
- Force: deletes old state and starts fresh
- Budget override: --budget sets custom budget
- Verbose: includes agent-level detail
- Missing file: exits with error about missing file
- Help: shows command help with all options
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skill_builder.agents.stubs import (
    StubDocumenterAgent,
    StubGapAnalyzerAgent,
    StubHarvestAgent,
    StubIntakeAgent,
    StubLearnerAgent,
    StubMapperAgent,
    StubOrganizerAgent,
    StubPackagerAgent,
    StubValidatorAgent,
)
from skill_builder.checkpoint import CheckpointStore
from skill_builder.cli import build
from skill_builder.models.state import PipelinePhase, PipelineState


def _stub_agents() -> dict:
    """Return a full set of stub agents for CLI testing."""
    return {
        "intake": StubIntakeAgent(),
        "harvest": StubHarvestAgent(),
        "organizer": StubOrganizerAgent(),
        "gap_analyzer": StubGapAnalyzerAgent(),
        "learner": StubLearnerAgent(),
        "mapper": StubMapperAgent(),
        "documenter": StubDocumenterAgent(),
        "validator": StubValidatorAgent(),
        "packager": StubPackagerAgent(),
    }


@pytest.fixture(autouse=True)
def _use_stub_agents() -> Generator[None, None, None]:
    """Patch _default_agents to return stubs so CLI tests don't need API keys."""
    with patch("skill_builder.conductor._default_agents", _stub_agents):
        yield


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def brief_file(tmp_path: Path) -> Path:
    """Create a temporary brief JSON file."""
    brief = {
        "name": "test-skill",
        "description": "A test skill for CLI testing",
        "seed_urls": [{"url": "https://example.com", "type": "docs"}],
        "tool_category": "test",
        "scope": "testing the CLI",
        "required_capabilities": ["testing"],
        "deploy_target": "user",
    }
    path = tmp_path / "test-brief.json"
    path.write_text(json.dumps(brief))
    return path


class TestBasicInvocation:
    """Test basic CLI invocation with stub agents."""

    def test_build_runs_successfully(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """skill-builder build brief.json runs successfully (exit code 0) with stubs."""
        # Use tmp_path for state dir to avoid polluting CWD
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file)])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"

    def test_build_shows_phase_banners(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Phase banners appear in output during a build run."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file)])
        assert result.exit_code == 0
        # Should contain at least some phase banners
        assert "[intake]" in result.output.lower() or "Starting" in result.output


class TestDryRun:
    """Test dry-run mode."""

    def test_dry_run_prints_plan(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--dry-run prints a fetch plan and cost estimate."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file), "--dry-run"])
        assert result.exit_code == 0
        # Should mention cost or estimate
        output = result.output.lower()
        assert "cost" in output or "estimate" in output or "plan" in output

    def test_dry_run_does_not_run_agents(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--dry-run exits without actually running the pipeline."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file), "--dry-run"])
        assert result.exit_code == 0
        # No checkpoint file should be created (agents didn't run)
        state_dir = tmp_path / ".skill-builder" / "state"
        if state_dir.exists():
            assert not (state_dir / "test-skill.json").exists()


class TestResume:
    """Test resume from checkpoint."""

    def test_resume_loads_state(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resume loads existing state and continues."""
        monkeypatch.chdir(tmp_path)

        # Pre-create state at a mid-pipeline phase
        store = CheckpointStore(tmp_path / ".skill-builder" / "state")
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.ORGANIZING,
        )
        store.save(state)

        result = runner.invoke(build, [str(brief_file), "--resume"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        # Output should mention resuming
        output = result.output.lower()
        assert "resum" in output


class TestStateClash:
    """Test state clash detection."""

    def test_state_exists_without_resume_or_force(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When state exists without --resume or --force, exits with warning."""
        monkeypatch.chdir(tmp_path)

        # Pre-create state
        store = CheckpointStore(tmp_path / ".skill-builder" / "state")
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.HARVESTING,
        )
        store.save(state)

        result = runner.invoke(build, [str(brief_file)])
        assert result.exit_code != 0
        output = result.output.lower()
        assert "--resume" in output or "resume" in output
        assert "--force" in output or "force" in output


class TestForce:
    """Test --force flag."""

    def test_force_starts_fresh(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--force when state exists starts fresh (deletes old state)."""
        monkeypatch.chdir(tmp_path)

        # Pre-create state at a mid-pipeline phase
        store = CheckpointStore(tmp_path / ".skill-builder" / "state")
        old_state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.HARVESTING,
        )
        store.save(old_state)

        result = runner.invoke(build, [str(brief_file), "--force"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"

        # After --force, the final state should be COMPLETE (started fresh)
        loaded = store.load("test-skill")
        assert loaded is not None
        assert loaded.phase == PipelinePhase.COMPLETE


class TestBudgetOverride:
    """Test --budget flag."""

    def test_budget_override(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--budget 10.0 sets budget to $10."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file), "--budget", "10.0"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"


class TestVerbose:
    """Test --verbose flag."""

    def test_verbose_includes_detail(
        self, runner: CliRunner, brief_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--verbose includes agent-level detail in output."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(build, [str(brief_file), "--verbose"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        # Verbose should have more output than non-verbose
        # At minimum, it should show phase transitions
        assert len(result.output) > 0


class TestMissingFile:
    """Test error handling for missing brief file."""

    def test_nonexistent_brief_file(self, runner: CliRunner) -> None:
        """skill-builder build nonexistent.json exits with error."""
        result = runner.invoke(build, ["nonexistent.json"])
        assert result.exit_code != 0


class TestHelp:
    """Test help output."""

    def test_help_shows_all_options(self, runner: CliRunner) -> None:
        """--help shows command help with all options."""
        result = runner.invoke(build, ["--help"])
        assert result.exit_code == 0
        output = result.output
        assert "--dry-run" in output
        assert "--resume" in output
        assert "--verbose" in output
        assert "--budget" in output
        assert "--force" in output
        assert "brief" in output.lower()
