"""Token budget tracker -- per-model pricing and budget enforcement.

Tracks cumulative token usage from Anthropic API response.usage fields,
converts to USD using per-model pricing, and reports budget status.
The conductor checks the budget after each agent call and halts if exceeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill_builder.models.state import PipelineState

logger = logging.getLogger(__name__)

# Verified pricing per million tokens (2026-03-05)
# Source: https://platform.claude.com/docs/en/about-claude/pricing
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
}

_DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class TokenBudget:
    """Tracks cumulative token usage and cost against a USD budget.

    Usage:
        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        if budget.exceeded:
            # halt pipeline
    """

    budget_usd: float = 25.0
    total_input_tokens: int = field(default=0)
    total_output_tokens: int = field(default=0)
    total_cost_usd: float = field(default=0.0)

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from response.usage and update cost.

        Falls back to Sonnet pricing for unknown model IDs.
        """
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        pricing = MODEL_PRICING.get(model, MODEL_PRICING[_DEFAULT_MODEL])
        cost = (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )
        self.total_cost_usd += cost

        logger.debug(
            "Usage: model=%s, in=%d, out=%d, cost=$%.4f, total=$%.4f",
            model, input_tokens, output_tokens, cost, self.total_cost_usd,
        )

    @property
    def exceeded(self) -> bool:
        """Whether total cost has reached or exceeded the budget."""
        return self.total_cost_usd >= self.budget_usd

    @property
    def remaining_usd(self) -> float:
        """Remaining budget in USD (never negative)."""
        return max(0.0, self.budget_usd - self.total_cost_usd)

    def sync_to_state(self, state: PipelineState) -> None:
        """Copy token and cost totals into PipelineState fields."""
        state.total_input_tokens = self.total_input_tokens
        state.total_output_tokens = self.total_output_tokens
        state.total_cost_usd = self.total_cost_usd
