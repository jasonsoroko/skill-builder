"""Tests for TokenBudget -- per-model token cost tracking with budget enforcement."""

from __future__ import annotations


class TestTokenBudget:
    """TokenBudget tracks cumulative token usage and reports budget status."""

    def test_record_usage_accumulates_tokens(self) -> None:
        """record_usage() adds input and output tokens to running totals."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        budget.record_usage("claude-sonnet-4-6", input_tokens=2000, output_tokens=1000)

        assert budget.total_input_tokens == 3000
        assert budget.total_output_tokens == 1500

    def test_record_usage_computes_cost_sonnet(self) -> None:
        """record_usage() computes cost using Sonnet 4.6 pricing ($3/$15 per MTok)."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        # 1M input tokens at $3/MTok = $3.00
        # 1M output tokens at $15/MTok = $15.00
        budget.record_usage("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)

        assert budget.total_cost_usd == 18.00  # $3 + $15

    def test_record_usage_computes_cost_opus(self) -> None:
        """record_usage() computes cost using Opus 4.6 pricing ($5/$25 per MTok)."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=100.0)
        # 1M input at $5/MTok = $5.00
        # 1M output at $25/MTok = $25.00
        budget.record_usage("claude-opus-4-6", input_tokens=1_000_000, output_tokens=1_000_000)

        assert budget.total_cost_usd == 30.00  # $5 + $25

    def test_record_usage_computes_cost_haiku(self) -> None:
        """record_usage() computes cost using Haiku 4.5 pricing ($1/$5 per MTok)."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000)

        assert budget.total_cost_usd == 6.00  # $1 + $5

    def test_unknown_model_falls_back_to_sonnet_pricing(self) -> None:
        """record_usage() uses Sonnet pricing as default for unknown model IDs."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("unknown-model-id", input_tokens=1_000_000, output_tokens=1_000_000)

        assert budget.total_cost_usd == 18.00  # Same as Sonnet: $3 + $15

    def test_exceeded_true_when_budget_reached(self) -> None:
        """exceeded returns True when total_cost_usd >= budget_usd."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=1.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)
        # Cost: 1M input at $3/MTok = $3.00 > $1.00 budget

        assert budget.exceeded is True

    def test_exceeded_false_when_under_budget(self) -> None:
        """exceeded returns False when total_cost_usd < budget_usd."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=100, output_tokens=50)

        assert budget.exceeded is False

    def test_remaining_usd(self) -> None:
        """remaining_usd returns the correct remaining amount."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)
        # Cost: $3.00, remaining = $22.00

        assert budget.remaining_usd == 22.00

    def test_remaining_usd_never_negative(self) -> None:
        """remaining_usd returns 0 when budget is exceeded, not a negative value."""
        from skill_builder.budget import TokenBudget

        budget = TokenBudget(budget_usd=1.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
        # Cost: $18.00, way over $1.00 budget

        assert budget.remaining_usd == 0.0

    def test_sync_to_state_copies_totals(self) -> None:
        """sync_to_state() copies token and cost totals to PipelineState fields."""
        from skill_builder.budget import TokenBudget
        from skill_builder.models.state import PipelineState

        budget = TokenBudget(budget_usd=25.0)
        budget.record_usage("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)

        state = PipelineState(brief_name="test-skill")
        budget.sync_to_state(state)

        assert state.total_input_tokens == 1000
        assert state.total_output_tokens == 500
        assert state.total_cost_usd == budget.total_cost_usd

    def test_model_pricing_contains_expected_models(self) -> None:
        """MODEL_PRICING dict contains entries for Sonnet, Opus, and Haiku."""
        from skill_builder.budget import MODEL_PRICING

        assert "claude-sonnet-4-6" in MODEL_PRICING
        assert "claude-opus-4-6" in MODEL_PRICING
        assert "claude-haiku-4-5-20251001" in MODEL_PRICING

    def test_model_pricing_values(self) -> None:
        """MODEL_PRICING has correct per-MTok pricing."""
        from skill_builder.budget import MODEL_PRICING

        assert MODEL_PRICING["claude-sonnet-4-6"]["input"] == 3.00
        assert MODEL_PRICING["claude-sonnet-4-6"]["output"] == 15.00
        assert MODEL_PRICING["claude-opus-4-6"]["input"] == 5.00
        assert MODEL_PRICING["claude-opus-4-6"]["output"] == 25.00
        assert MODEL_PRICING["claude-haiku-4-5-20251001"]["input"] == 1.00
        assert MODEL_PRICING["claude-haiku-4-5-20251001"]["output"] == 5.00
