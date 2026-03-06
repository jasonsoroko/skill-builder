"""Layer 4: Conductor E2E tests -- state machine, checkpointing, budget, resume.

Exercises the full pipeline with real agents and real APIs:
1. Fresh run to COMPLETE
2. Budget halt (impossibly small budget)
3. Resume from checkpoint
4. CLI dry-run (no API calls)
5. CLI verbose run

Total cost: ~$2.00. Run with: pytest -m live tests/test_live_conductor.py --tb=short -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skill_builder.budget import TokenBudget
from skill_builder.checkpoint import CheckpointStore
from skill_builder.conductor import Conductor
from skill_builder.models.brief import SkillBrief
from skill_builder.models.state import PipelinePhase

pytestmark = [pytest.mark.live, pytest.mark.timeout(600)]

# Same minimal brief from Layer 3
_BRIEF_DICT = {
    "name": "exa-search-test",
    "description": "Test skill for Exa semantic search",
    "seed_urls": [{"url": "https://docs.exa.ai/", "type": "docs"}],
    "tool_category": "research",
    "scope": "Using Exa for semantic search",
    "required_capabilities": ["semantic search", "result filtering"],
    "deploy_target": "package",
    "target_api_version": None,
    "max_pages": 5,
}


def _skip_if_no_keys() -> None:
    """Skip if any required API key is missing."""
    for key in ("ANTHROPIC_API_KEY", "FIRECRAWL_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY"):
        if not os.environ.get(key):
            pytest.skip(f"{key} not set")


@pytest.fixture
def brief() -> SkillBrief:
    return SkillBrief(**_BRIEF_DICT)


@pytest.fixture
def brief_json(tmp_path: Path) -> Path:
    """Write a brief JSON file to tmp_path and return the path."""
    p = tmp_path / "exa-only.json"
    p.write_text(json.dumps(_BRIEF_DICT, indent=2))
    return p


def _patch_packager_output(tmp_path: Path):
    """Return a context manager that redirects packager output to tmp_path."""
    import skill_builder.agents.packager as pkg_mod

    return patch.object(
        pkg_mod,
        "_resolve_deploy_path",
        side_effect=lambda target, name: tmp_path / "output" / name,
    )


class TestConductorFreshRun:
    """Full E2E: real agents, real APIs, assert COMPLETE."""

    def test_conductor_fresh_run(self, brief: SkillBrief, tmp_path: Path) -> None:
        """Conductor runs all real agents to COMPLETE with checkpoint and output."""
        _skip_if_no_keys()

        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=10.0)

        with _patch_packager_output(tmp_path):
            conductor = Conductor(brief=brief, store=store, budget=budget)
            result = conductor.run()

        # State machine reached terminal
        assert result.phase in (PipelinePhase.COMPLETE, PipelinePhase.FAILED), (
            f"Unexpected terminal phase: {result.phase}"
        )

        if result.phase == PipelinePhase.FAILED:
            pytest.fail(f"Pipeline FAILED: {result.error}")

        # Budget tracking worked (real agents report _usage_meta)
        assert result.total_cost_usd > 0, "Expected non-zero cost from real agents"

        # Evaluation happened
        assert len(result.evaluation_results) >= 1, "Expected at least 1 evaluation"

        # Checkpoint file exists
        assert store.exists("exa-search-test"), "Checkpoint file missing"

        # Output directory created with SKILL.md
        output_dir = tmp_path / "output" / "exa-search-test"
        assert (output_dir / "SKILL.md").exists(), "SKILL.md missing from output"
        assert (output_dir / "SETUP.md").exists(), "SETUP.md missing from output"


class TestConductorBudgetHalt:
    """Budget enforcement: pipeline halts when budget exceeded."""

    def test_conductor_budget_halt(self, brief: SkillBrief, tmp_path: Path) -> None:
        """Conductor halts early with impossibly small budget."""
        _skip_if_no_keys()

        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=0.01)

        with _patch_packager_output(tmp_path):
            conductor = Conductor(brief=brief, store=store, budget=budget)
            result = conductor.run()

        # Pipeline should NOT reach COMPLETE
        assert result.phase != PipelinePhase.COMPLETE, (
            "Pipeline should have halted due to budget"
        )

        # Some cost was recorded before halt
        assert result.total_cost_usd > 0, "Expected some cost before budget halt"

        # State was checkpointed for resume
        assert store.exists("exa-search-test"), "Checkpoint missing after budget halt"


class TestConductorResume:
    """Resume from checkpoint: halt then continue."""

    def test_conductor_resume_from_checkpoint(
        self, brief: SkillBrief, tmp_path: Path
    ) -> None:
        """Run with low budget, halt, then resume with high budget to COMPLETE."""
        _skip_if_no_keys()

        store = CheckpointStore(tmp_path / "state")

        # Phase 1: Run with small budget — should halt partway through
        budget_low = TokenBudget(budget_usd=0.50)
        with _patch_packager_output(tmp_path):
            conductor1 = Conductor(brief=brief, store=store, budget=budget_low)
            result1 = conductor1.run()

        halted_phase = result1.phase
        assert halted_phase != PipelinePhase.COMPLETE, (
            "Expected pipeline to halt before COMPLETE with $0.50 budget"
        )
        assert halted_phase != PipelinePhase.INITIALIZED, (
            "Expected pipeline to progress past INITIALIZED"
        )

        # Phase 2: Load checkpoint and resume with generous budget
        loaded = store.load("exa-search-test")
        assert loaded is not None, "Checkpoint not found for resume"
        assert loaded.phase == halted_phase

        budget_high = TokenBudget(budget_usd=10.0)
        with _patch_packager_output(tmp_path):
            conductor2 = Conductor(brief=brief, store=store, budget=budget_high)
            result2 = conductor2.run(state=loaded)

        # Should progress further than where it halted
        # The ordering of phases as an enum means we can't easily compare,
        # so just check it reached COMPLETE or went past the halt point
        assert result2.phase in (PipelinePhase.COMPLETE, PipelinePhase.FAILED), (
            f"Expected COMPLETE or FAILED after resume, got {result2.phase}"
        )

        if result2.phase == PipelinePhase.FAILED:
            pytest.fail(f"Pipeline FAILED after resume: {result2.error}")


class TestCLIDryRun:
    """CLI --dry-run: no API calls, just shows plan."""

    @pytest.mark.timeout(10)
    def test_cli_dry_run(self, brief_json: Path, tmp_path: Path) -> None:
        """Dry-run shows fetch plan and exits cleanly with no API calls."""
        from skill_builder.cli import build

        runner = CliRunner()

        # Patch state dir to tmp_path so we don't pollute the real one
        with patch("skill_builder.cli._STATE_DIR", tmp_path / "state"):
            result = runner.invoke(build, [str(brief_json), "--dry-run"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Fetch Plan" in result.output
        assert "docs.exa.ai" in result.output

        # No checkpoint created (dry-run doesn't execute)
        assert not (tmp_path / "state" / "exa-search-test.json").exists(), (
            "Dry-run should not create checkpoint"
        )


class TestCLIVerboseRun:
    """CLI --verbose: full pipeline run via Click."""

    def test_cli_verbose_run(self, brief_json: Path, tmp_path: Path) -> None:
        """CLI runs pipeline with --verbose and --budget, shows phase output."""
        _skip_if_no_keys()

        from skill_builder.cli import build

        runner = CliRunner()

        with _patch_packager_output(tmp_path), \
             patch("skill_builder.cli._STATE_DIR", tmp_path / "state"):
            result = runner.invoke(
                build,
                [str(brief_json), "--verbose", "--budget", "10.0", "--force"],
            )

        # Exit code 0 = COMPLETE, 1 = FAILED
        assert result.exit_code in (0, 1), (
            f"Unexpected exit code {result.exit_code}: {result.output}"
        )

        # Output should contain phase status lines
        assert "Starting" in result.output, "Expected phase start lines in verbose output"

        if result.exit_code == 0:
            assert "Build Complete" in result.output
        else:
            # FAILED or budget halt — still valid
            assert "failed" in result.output.lower() or "halted" in result.output.lower()
