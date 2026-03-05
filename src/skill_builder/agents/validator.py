"""ValidatorAgent -- orchestrates 5 evaluators with fail-fast and parallel execution.

Runs heuristic evaluators (compactness, syntax) first. If either fails, returns
immediately without invoking the 3 expensive Opus LLM-as-judge evaluators.
When heuristics pass, runs all 3 LLM evaluators in parallel via asyncio.gather.

Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.evaluators.api_accuracy import evaluate_api_accuracy
from skill_builder.evaluators.compactness import check_compactness
from skill_builder.evaluators.completeness import evaluate_completeness
from skill_builder.evaluators.syntax import check_syntax
from skill_builder.evaluators.trigger_quality import evaluate_trigger_quality
from skill_builder.models.brief import SkillBrief
from skill_builder.models.evaluation import EvaluationDimension, EvaluationResult
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Orchestrates 5 evaluators with fail-fast heuristics and parallel LLM execution.

    Conforms to BaseAgent Protocol: run(**kwargs) -> EvaluationResult.

    Phase 1 - Heuristics (fail-fast):
        If compactness or syntax fails, return immediately with only heuristic
        dimensions. This saves cost by skipping the 3 Opus LLM evaluator calls.

    Phase 2 - LLM evaluators (parallel):
        Run api_accuracy, completeness, and trigger_quality in parallel via
        asyncio.gather. Combine all 5 dimensions for the final result.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> EvaluationResult:
        """Execute the validation phase.

        Expected kwargs:
            skill_draft: dict -- SkillDraft as dict
            setup_draft: dict -- SetupDraft as dict
            knowledge_model: dict -- KnowledgeModel as dict
            brief: SkillBrief
            categorized_research: dict | None -- organized research for API accuracy check
            iteration: int -- validation iteration (1-based)
        """
        skill_draft: dict = kwargs["skill_draft"]
        knowledge_model: dict = kwargs["knowledge_model"]
        brief: SkillBrief = kwargs["brief"]
        categorized_research: dict | None = kwargs.get("categorized_research")
        iteration: int = kwargs.get("iteration", 1)

        skill_content: str = skill_draft["content"]

        # Phase 1: Heuristics (fail-fast)
        compactness_dim = check_compactness(skill_content)
        syntax_dim = check_syntax(skill_content)

        heuristic_dims = [compactness_dim, syntax_dim]
        heuristic_failed = any(not d.passed for d in heuristic_dims)

        if heuristic_failed:
            logger.info(
                "ValidatorAgent: heuristics failed (compactness=%s, syntax=%s). "
                "Skipping LLM evaluators.",
                compactness_dim.passed,
                syntax_dim.passed,
            )
            return EvaluationResult(
                dimensions=heuristic_dims,
                overall_pass=False,
                iteration=iteration,
            )

        # Phase 2: LLM evaluators (parallel)
        logger.info("ValidatorAgent: heuristics passed. Running LLM evaluators in parallel.")

        organized_research = categorized_research or {}

        async def _parallel() -> list[EvaluationDimension]:
            return list(
                await asyncio.gather(
                    evaluate_api_accuracy(self.client, skill_content, organized_research),
                    evaluate_completeness(self.client, skill_content, knowledge_model),
                    evaluate_trigger_quality(self.client, skill_content, knowledge_model),
                )
            )

        # Sync-to-async bridge (same pattern as HarvestAgent)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _parallel())
                llm_dims = future.result()
        else:
            llm_dims = asyncio.run(_parallel())

        # Accumulate usage metadata from all 3 LLM evaluator results
        _accumulated_usage = {"model": "claude-opus-4-6", "input_tokens": 0, "output_tokens": 0}
        for dim in llm_dims:
            dim_meta = getattr(dim, "_usage_meta", None)
            if dim_meta:
                _accumulated_usage["input_tokens"] += dim_meta["input_tokens"]
                _accumulated_usage["output_tokens"] += dim_meta["output_tokens"]
                _accumulated_usage["model"] = dim_meta["model"]

        # Combine all 5 dimensions
        all_dims = heuristic_dims + llm_dims
        overall_pass = all(d.passed for d in all_dims)

        logger.info(
            "ValidatorAgent: complete. %d/5 passed, overall=%s",
            sum(1 for d in all_dims if d.passed),
            overall_pass,
        )

        eval_result = EvaluationResult(
            dimensions=all_dims,
            overall_pass=overall_pass,
            iteration=iteration,
        )
        if _accumulated_usage["input_tokens"] > 0 or _accumulated_usage["output_tokens"] > 0:
            eval_result._usage_meta = _accumulated_usage  # type: ignore[attr-defined]

        return eval_result
