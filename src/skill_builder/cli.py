"""Click CLI entry point for skill-builder.

Provides the `skill-builder build` command that drives stub agents (Phase 1)
through the full pipeline with checkpoint persistence, resume capability,
budget enforcement, and dry-run mode.

Usage:
    skill-builder build brief.json [--dry-run] [--resume] [--verbose] [--budget N] [--force]
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from skill_builder.budget import TokenBudget
from skill_builder.checkpoint import CheckpointStore
from skill_builder.conductor import Conductor
from skill_builder.models.brief import SkillBrief
from skill_builder.models.state import PipelinePhase, PipelineState

# Default state directory (relative to CWD)
_STATE_DIR = Path(".skill-builder") / "state"


@click.command()
@click.argument("brief", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Show fetch plan and cost estimate, then exit")
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.option("--verbose", is_flag=True, help="Show agent-level detail")
@click.option("--budget", type=float, default=25.0, help="Global token budget in USD (default $25)")
@click.option("--force", is_flag=True, help="Overwrite existing state")
def build(
    brief: Path,
    dry_run: bool,
    resume: bool,
    verbose: bool,
    budget: float,
    force: bool,
) -> None:
    """Build a Claude Code skill from a skill brief."""
    # 1. Load and validate brief
    try:
        raw = json.loads(brief.read_text())
        skill_brief = SkillBrief.model_validate(raw)
    except Exception as exc:
        click.echo(f"Error loading brief: {exc}", err=True)
        raise SystemExit(1) from exc

    brief_name = skill_brief.brief_name

    if verbose:
        click.echo(f"  Loaded brief: {skill_brief.name} ({brief_name})")

    # 2. Create CheckpointStore
    store = CheckpointStore(_STATE_DIR)

    # 3. State clash detection
    state: PipelineState | None = None

    if store.exists(brief_name) and not resume and not force:
        click.echo(
            f"State exists for '{brief_name}'. "
            "Use --resume to continue or --force to start fresh."
        )
        raise SystemExit(1)

    if force and store.exists(brief_name):
        # Delete existing state file
        state_path = store._path(brief_name)
        state_path.unlink()
        if verbose:
            click.echo(f"  Deleted existing state for '{brief_name}'")

    # 4. Create TokenBudget
    token_budget = TokenBudget(budget_usd=budget)

    # 5. Resume handling
    if resume:
        state = store.load(brief_name)
        if state is not None:
            click.echo(
                f"Resuming '{brief_name}' from [{state.phase.value}]. Continuing..."
            )
        else:
            click.echo(f"No checkpoint found for '{brief_name}'. Starting fresh.")

    # 6. Dry-run mode
    if dry_run:
        _print_dry_run(skill_brief, token_budget)
        return

    # 7. Create Conductor and run
    conductor = Conductor(
        brief=skill_brief,
        store=store,
        budget=token_budget,
    )

    if verbose:
        click.echo(f"  Budget: ${budget:.2f}")
        click.echo("")

    result = conductor.run(state=state)

    # 8. Print completion summary
    click.echo("")
    if result.phase == PipelinePhase.COMPLETE:
        click.echo(f"  Build complete: {brief_name}")
        click.echo(
            f"  Cost: ${result.total_cost_usd:.4f}"
            f" (budget: ${budget:.2f})"
        )
    elif result.phase == PipelinePhase.FAILED:
        click.echo(f"  Build failed: {brief_name}")
        if result.error:
            click.echo(f"  Error: {result.error}")
        raise SystemExit(1)
    else:
        # Budget exceeded or other halt
        click.echo(f"  Build halted at [{result.phase.value}]: {brief_name}")
        click.echo(
            f"  Cost: ${result.total_cost_usd:.4f}"
            f" (budget: ${budget:.2f})"
        )
        click.echo("  Use --resume to continue with a higher --budget.")


def _print_dry_run(brief: SkillBrief, budget: TokenBudget) -> None:
    """Print fetch plan and cost estimate for dry-run mode."""
    click.echo(f"  Dry-run: {brief.name} ({brief.brief_name})")
    click.echo("")

    # URLs to crawl
    click.echo("  Fetch Plan:")
    for url in brief.seed_urls:
        click.echo(f"    [{url.type}] {url.url}")
    click.echo("")

    # Agents to invoke (all pipeline phases)
    phases = [
        ("intake", "Validate brief"),
        ("harvesting", "Crawl seed URLs"),
        ("organizing", "Categorize research"),
        ("gap_analyzing", "Analyze coverage gaps"),
        ("learning", "Build knowledge model"),
        ("mapping", "Draft SKILL.md"),
        ("documenting", "Draft SETUP.md"),
        ("validating", "Evaluate skill quality"),
        ("packaging", "Package output files"),
    ]
    click.echo("  Pipeline Phases:")
    for phase_name, description in phases:
        click.echo(f"    {phase_name:20s} {description}")
    click.echo("")

    # Cost estimate
    # Estimated tokens per phase (stub values for Phase 1)
    est_input_per_phase = 2000
    est_output_per_phase = 1000
    num_phases = len(phases)
    # Add potential re-harvest and re-validation loops
    max_loops = 2 + 2  # gap + validation
    total_phases = num_phases + max_loops

    # Use Sonnet pricing as default estimate
    input_cost = total_phases * est_input_per_phase / 1_000_000 * 3.00
    output_cost = total_phases * est_output_per_phase / 1_000_000 * 15.00
    estimated_total = input_cost + output_cost

    click.echo("  Cost Estimate (using claude-sonnet-4-6 pricing):")
    click.echo(f"    Phases:          {num_phases} (+ up to {max_loops} feedback loops)")
    click.echo(f"    Est. input:      ~{total_phases * est_input_per_phase:,} tokens")
    click.echo(f"    Est. output:     ~{total_phases * est_output_per_phase:,} tokens")
    click.echo(f"    Est. cost:       ~${estimated_total:.4f}")
    click.echo(f"    Budget:          ${budget.budget_usd:.2f}")
    click.echo("")
    click.echo("  (Estimates based on stub agent profiles. Real costs may vary.)")


def main() -> None:
    """Entry point for the skill-builder CLI."""
    build()
