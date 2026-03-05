"""PipelineProgress -- Rich CLI progress display with TTY detection and fallback.

Provides a live status display during pipeline execution showing current phase,
active agent, iteration count, and elapsed time. Degrades gracefully to plain
text log lines when not running in a terminal (non-TTY).

The final summary panel provides a complete build receipt: time, cost, scores,
feedback loop counts, output path, and verification instructions.
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class PipelineProgress:
    """Rich CLI progress display with TTY detection and fallback.

    When running in a terminal, uses Rich formatting for clean output.
    When not a TTY (CI, pipes, etc.), degrades to plain text lines.

    Usage:
        progress = PipelineProgress(verbose=True)
        progress.phase_start("harvesting", "harvest")
        progress.phase_complete("harvesting", 2.5)
        progress.summary_panel(total_time=42.5, ...)
    """

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._console = Console()
        self._phase: str = ""
        self._agent: str = ""
        self._iteration: int = 0
        self._elapsed: float = 0.0
        self._start_time: float = time.monotonic()

    def phase_start(self, phase: str, agent: str) -> None:
        """Record and display phase start.

        Args:
            phase: The pipeline phase name (e.g., "harvesting").
            agent: The agent key (e.g., "harvest").
        """
        self._phase = phase
        self._agent = agent
        self._iteration += 1

        if self._console.is_terminal:
            self._console.print(
                f"  [bold cyan][{phase}][/bold cyan] Starting {agent}..."
            )
        else:
            self._console.print(f"  [{phase}] Starting {agent}...")

    def phase_complete(self, phase: str, elapsed: float) -> None:
        """Record and display phase completion.

        Args:
            phase: The pipeline phase name.
            elapsed: Time in seconds the phase took.
        """
        self._elapsed = elapsed

        if self._console.is_terminal:
            self._console.print(
                f"  [bold green][{phase}][/bold green] Complete ({elapsed:.1f}s)"
            )
        else:
            self._console.print(f"  [{phase}] Complete ({elapsed:.1f}s)")

    def eval_score(self, name: str, score: int, passed: bool) -> None:
        """Display an evaluation score.

        Per CONTEXT.md: "Evaluator scores should display as 9/10 PASS or 4/10 FAIL"

        Args:
            name: Dimension name (e.g., "api_accuracy").
            score: Score out of 10.
            passed: Whether the dimension passed.
        """
        status = "PASS" if passed else "FAIL"

        if self._console.is_terminal:
            color = "green" if passed else "red"
            self._console.print(
                f"    {name}: [{color}]{score}/10 {status}[/{color}]"
            )
        else:
            self._console.print(f"    {name}: {score}/10 {status}")

    def budget_display(self, spent: float, budget_total: float) -> None:
        """Display budget status.

        Per CONTEXT.md: "$5.82 / $25.00 (23.3%)"
        Only shown when verbose=True (caller should check).

        Args:
            spent: Amount spent in USD.
            budget_total: Total budget in USD.
        """
        pct = (spent / budget_total * 100) if budget_total > 0 else 0.0

        if self._console.is_terminal:
            self._console.print(
                f"  [dim]Budget: ${spent:.2f} / ${budget_total:.2f} ({pct:.1f}%)[/dim]"
            )
        else:
            self._console.print(
                f"  Budget: ${spent:.2f} / ${budget_total:.2f} ({pct:.1f}%)"
            )

    def summary_panel(
        self,
        total_time: float,
        total_cost: float,
        eval_dimensions: list[dict[str, Any]],
        gap_loops: int,
        validation_loops: int,
        output_path: str,
        verification_instructions: str,
    ) -> None:
        """Display the final build receipt as a Rich Panel.

        Per CONTEXT.md: "The final summary panel should feel like a build receipt:
        time, cost, scores, output path, next step"

        Args:
            total_time: Total pipeline time in seconds.
            total_cost: Total cost in USD.
            eval_dimensions: List of evaluation dimension dicts.
            gap_loops: Number of gap analysis re-harvest loops.
            validation_loops: Number of validation re-production loops.
            output_path: Path to the output directory.
            verification_instructions: Human-readable verification steps.
        """
        if self._console.is_terminal:
            self._render_rich_summary(
                total_time, total_cost, eval_dimensions,
                gap_loops, validation_loops, output_path,
                verification_instructions,
            )
        else:
            self._render_plain_summary(
                total_time, total_cost, eval_dimensions,
                gap_loops, validation_loops, output_path,
                verification_instructions,
            )

    def _render_rich_summary(
        self,
        total_time: float,
        total_cost: float,
        eval_dimensions: list[dict[str, Any]],
        gap_loops: int,
        validation_loops: int,
        output_path: str,
        verification_instructions: str,
    ) -> None:
        """Render summary as a Rich Panel with Table."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("Time", f"{total_time:.1f}s")
        table.add_row("Cost", f"${total_cost:.4f}")
        table.add_row("Gap loops", str(gap_loops))
        table.add_row("Validation loops", str(validation_loops))
        table.add_row("Output", output_path)

        # Add evaluation scores
        if eval_dimensions:
            scores_parts = []
            for dim in eval_dimensions:
                status = "PASS" if dim.get("passed") else "FAIL"
                color = "green" if dim.get("passed") else "red"
                scores_parts.append(
                    f"[{color}]{dim['name']}: {dim['score']}/10 {status}[/{color}]"
                )
            scores_text = ", ".join(scores_parts)
            table.add_row("Scores", scores_text)

        panel = Panel(
            table,
            title="[bold]Build Complete[/bold]",
            border_style="green",
        )
        self._console.print()
        self._console.print(panel)

        # Verification instructions below the panel
        if verification_instructions:
            self._console.print()
            self._console.print(f"[dim]{verification_instructions}[/dim]")

    def _render_plain_summary(
        self,
        total_time: float,
        total_cost: float,
        eval_dimensions: list[dict[str, Any]],
        gap_loops: int,
        validation_loops: int,
        output_path: str,
        verification_instructions: str,
    ) -> None:
        """Render summary as plain text lines for non-TTY."""
        self._console.print("")
        self._console.print("  Build Complete")
        self._console.print(f"  Time: {total_time:.1f}s")
        self._console.print(f"  Cost: ${total_cost:.4f}")
        self._console.print(f"  Gap loops: {gap_loops}")
        self._console.print(f"  Validation loops: {validation_loops}")

        if eval_dimensions:
            for dim in eval_dimensions:
                status = "PASS" if dim.get("passed") else "FAIL"
                self._console.print(
                    f"    {dim['name']}: {dim['score']}/10 {status}"
                )

        self._console.print(f"  Output: {output_path}")

        if verification_instructions:
            self._console.print("")
            self._console.print(f"  {verification_instructions}")
