"""Conductor -- deterministic state machine driving the skill-builder pipeline.

The conductor transitions through all pipeline phases using a static transition
table, dispatches to the appropriate agent for each phase, handles feedback loops
(gap analysis and validation), persists state at every phase boundary, enforces
budget limits, and supports resume from any checkpoint.

Phase banners use clean, informative output inspired by uv/ruff style.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from skill_builder.progress import PipelineProgress

from skill_builder.agents.documenter import DocumenterAgent
from skill_builder.agents.gap_analyzer import GapAnalyzerAgent
from skill_builder.agents.harvest import HarvestAgent
from skill_builder.agents.learner import LearnerAgent
from skill_builder.agents.mapper import MapperAgent
from skill_builder.agents.organizer import OrganizerAgent
from skill_builder.agents.packager import PackagerAgent
from skill_builder.agents.stubs import StubIntakeAgent
from skill_builder.agents.validator import ValidatorAgent
from skill_builder.budget import TokenBudget
from skill_builder.checkpoint import CheckpointStore
from skill_builder.models.brief import SkillBrief
from skill_builder.models.evaluation import EvaluationResult
from skill_builder.models.state import PipelinePhase, PipelineState
from skill_builder.models.synthesis import GapReport

logger = logging.getLogger(__name__)

# Sentinel value for conditional transitions (gap/validation loops)
_CONDITIONAL = "conditional"


def _default_agents() -> dict[str, Any]:
    """Create the default agent set.

    Phase 2 agents (harvest, organizer, gap_analyzer, learner) use real implementations.
    Phase 3 agents (mapper, documenter, validator, packager) use real implementations.
    Only intake still uses a stub until implemented.
    """
    return {
        "intake": StubIntakeAgent(),
        "harvest": HarvestAgent(),
        "organizer": OrganizerAgent(),
        "gap_analyzer": GapAnalyzerAgent(),
        "learner": LearnerAgent(),
        "mapper": MapperAgent(),
        "documenter": DocumenterAgent(),
        "validator": ValidatorAgent(),
        "packager": PackagerAgent(),
    }


class Conductor:
    """Deterministic state machine driving the skill-builder pipeline.

    The conductor reads a transition table to determine the next phase after
    each agent completes. Two feedback loops (gap analysis, validation) use
    conditional transitions with hard iteration caps.

    Usage:
        conductor = Conductor(brief, store, budget)
        result = conductor.run()  # fresh run
        result = conductor.run(state=saved_state)  # resume
    """

    MAX_GAP_LOOPS: int = 2
    MAX_VALIDATION_LOOPS: int = 2

    # Static transition table: current phase -> next phase
    # "conditional" entries are resolved dynamically in _next_phase()
    TRANSITION_TABLE: dict[PipelinePhase, PipelinePhase | str] = {
        PipelinePhase.INITIALIZED: PipelinePhase.INTAKE,
        PipelinePhase.INTAKE: PipelinePhase.HARVESTING,
        PipelinePhase.HARVESTING: PipelinePhase.ORGANIZING,
        PipelinePhase.ORGANIZING: PipelinePhase.GAP_ANALYZING,
        PipelinePhase.GAP_ANALYZING: _CONDITIONAL,  # -> LEARNING or RE_HARVESTING
        PipelinePhase.RE_HARVESTING: PipelinePhase.GAP_ANALYZING,
        PipelinePhase.LEARNING: PipelinePhase.MAPPING,
        PipelinePhase.MAPPING: PipelinePhase.DOCUMENTING,
        PipelinePhase.DOCUMENTING: PipelinePhase.VALIDATING,
        PipelinePhase.VALIDATING: _CONDITIONAL,  # -> PACKAGING or RE_PRODUCING
        PipelinePhase.RE_PRODUCING: PipelinePhase.VALIDATING,
        PipelinePhase.PACKAGING: PipelinePhase.COMPLETE,
    }

    # Maps phases to agent keys for dispatch
    _PHASE_AGENT_MAP: dict[PipelinePhase, str] = {
        PipelinePhase.INTAKE: "intake",
        PipelinePhase.HARVESTING: "harvest",
        PipelinePhase.ORGANIZING: "organizer",
        PipelinePhase.GAP_ANALYZING: "gap_analyzer",
        PipelinePhase.RE_HARVESTING: "harvest",
        PipelinePhase.LEARNING: "learner",
        PipelinePhase.MAPPING: "mapper",
        PipelinePhase.DOCUMENTING: "documenter",
        PipelinePhase.VALIDATING: "validator",
        PipelinePhase.RE_PRODUCING: "mapper",
        PipelinePhase.PACKAGING: "packager",
    }

    def __init__(
        self,
        brief: SkillBrief,
        store: CheckpointStore,
        budget: TokenBudget,
        agents: dict[str, Any] | None = None,
        progress: PipelineProgress | None = None,
    ) -> None:
        self.brief = brief
        self.store = store
        self.budget = budget
        self.agents = agents if agents is not None else _default_agents()
        self.progress = progress

    def run(self, state: PipelineState | None = None) -> PipelineState:
        """Run the pipeline from the given state (or fresh start).

        Args:
            state: Existing state to resume from. If None, creates a new state.

        Returns:
            The final PipelineState after execution completes, halts, or fails.
        """
        if state is None:
            state = PipelineState(brief_name=self.brief.brief_name)

        while state.phase not in (PipelinePhase.COMPLETE, PipelinePhase.FAILED):
            # Determine the next phase to execute
            next_phase = self._next_phase(state.phase, state)

            if next_phase in (PipelinePhase.COMPLETE, PipelinePhase.FAILED):
                state.phase = next_phase
                self.store.save(state)
                self.budget.sync_to_state(state)
                break

            # Transition to the next phase
            state.phase = next_phase

            # Run the agent for this phase
            try:
                state = self._run_phase(state.phase, state)
            except Exception as exc:
                logger.exception("Agent failed at phase %s: %s", state.phase, exc)
                state.phase = PipelinePhase.FAILED
                state.error = f"{type(exc).__name__}: {exc}"
                self.store.save(state)
                self.budget.sync_to_state(state)
                return state

            # Save checkpoint after phase completion
            self.budget.sync_to_state(state)
            self.store.save(state)

            # Check budget after each agent
            if self.budget.exceeded:
                logger.warning(
                    "Budget exceeded ($%.2f / $%.2f). Halting pipeline at phase %s.",
                    self.budget.total_cost_usd,
                    self.budget.budget_usd,
                    state.phase,
                )
                if self.progress:
                    self.progress.budget_display(
                        self.budget.total_cost_usd, self.budget.budget_usd
                    )
                else:
                    print(
                        f"  [budget] Exceeded (${self.budget.total_cost_usd:.2f}"
                        f" / ${self.budget.budget_usd:.2f}). Halting."
                    )
                return state

        return state

    def _run_phase(self, phase: PipelinePhase, state: PipelineState) -> PipelineState:
        """Dispatch to the appropriate agent for the given phase.

        Passes focused kwargs per phase so each agent receives only the
        data it needs (Pattern 4 from RESEARCH.md).

        Args:
            phase: The current pipeline phase.
            state: The current pipeline state.

        Returns:
            Updated pipeline state with agent output stored.
        """
        agent_key = self._PHASE_AGENT_MAP.get(phase)
        if agent_key is None:
            return state

        agent = self.agents.get(agent_key)
        if agent is None:
            logger.warning("No agent registered for phase %s (key=%s)", phase, agent_key)
            return state

        phase_label = phase.value
        if self.progress:
            self.progress.phase_start(phase_label, agent_key)
        else:
            print(f"  [{phase_label}] Starting...")
        start = time.monotonic()

        kwargs = self._build_kwargs(phase, state)
        result = agent.run(**kwargs)
        elapsed = time.monotonic() - start

        # Record token usage if agent provides metadata
        usage_meta = getattr(result, "_usage_meta", None)
        if usage_meta:
            self.budget.record_usage(
                usage_meta["model"],
                input_tokens=usage_meta["input_tokens"],
                output_tokens=usage_meta["output_tokens"],
            )

        # Store result in state based on phase
        self._store_result(phase, state, result)

        if self.progress:
            self.progress.phase_complete(phase_label, elapsed)
        else:
            print(f"  [{phase_label}] Complete ({elapsed:.1f}s)")

        # Display eval scores after validation
        if phase == PipelinePhase.VALIDATING and self.progress:
            dumped = result.model_dump() if hasattr(result, "model_dump") else result
            for dim in dumped.get("dimensions", []):
                self.progress.eval_score(dim["name"], dim["score"], dim["passed"])

        # Display budget at phase boundaries when verbose
        if self.progress and self.progress.verbose:
            self.progress.budget_display(
                self.budget.total_cost_usd, self.budget.budget_usd
            )

        return state

    def _build_kwargs(
        self, phase: PipelinePhase, state: PipelineState
    ) -> dict[str, Any]:
        """Build focused kwargs for an agent based on the current phase.

        Each agent receives only the data it needs. The conductor is the only
        component that reads/writes PipelineState.
        """
        if phase == PipelinePhase.INTAKE:
            return {"brief": self.brief}

        if phase in (PipelinePhase.HARVESTING, PipelinePhase.RE_HARVESTING):
            return {"brief": self.brief, "state": state}

        if phase == PipelinePhase.ORGANIZING:
            return {"raw_harvest": state.raw_harvest, "brief": self.brief}

        if phase == PipelinePhase.GAP_ANALYZING:
            kwargs: dict[str, Any] = {
                "categorized_research": state.categorized_research,
                "brief": self.brief,
            }
            # Pass harvest warnings if available in raw_harvest
            if state.raw_harvest:
                warnings = state.raw_harvest.get("warnings", [])
                if warnings:
                    kwargs["harvest_warnings"] = warnings
            return kwargs

        if phase == PipelinePhase.LEARNING:
            return {
                "categorized_research": state.categorized_research,
                "gap_report": state.gap_report,
                "brief": self.brief,
            }

        if phase == PipelinePhase.MAPPING:
            return {
                "knowledge_model": state.knowledge_model,
                "brief": self.brief,
            }

        if phase == PipelinePhase.DOCUMENTING:
            return {
                "knowledge_model": state.knowledge_model,
                "brief": self.brief,
            }

        if phase == PipelinePhase.VALIDATING:
            return {
                "skill_draft": state.skill_draft,
                "setup_draft": state.setup_draft,
                "knowledge_model": state.knowledge_model,
                "brief": self.brief,
                "categorized_research": state.categorized_research,
                "iteration": state.validation_loop_count + 1,
            }

        if phase == PipelinePhase.RE_PRODUCING:
            kwargs: dict[str, Any] = {
                "knowledge_model": state.knowledge_model,
                "brief": self.brief,
            }
            # Extract failed dimensions from last evaluation
            if state.evaluation_results:
                last_eval = state.evaluation_results[-1]
                failed = [
                    d for d in last_eval.get("dimensions", [])
                    if not d.get("passed", True)
                ]
                if failed:
                    kwargs["failed_dimensions"] = failed
            return kwargs

        if phase == PipelinePhase.PACKAGING:
            return {
                "skill_draft": state.skill_draft,
                "setup_draft": state.setup_draft,
                "brief": self.brief,
            }

        # Fallback for unknown phases
        return {}

    def _store_result(self, phase: PipelinePhase, state: PipelineState, result: Any) -> None:
        """Store agent output in the appropriate state field."""
        if hasattr(result, "model_dump"):
            dumped = result.model_dump()
        elif isinstance(result, dict):
            dumped = result
        else:
            dumped = {"raw": str(result)}

        if phase == PipelinePhase.INTAKE:
            pass  # Brief validation, no state field needed
        elif phase == PipelinePhase.HARVESTING:
            state.raw_harvest = dumped
        elif phase == PipelinePhase.ORGANIZING:
            state.categorized_research = dumped
        elif phase == PipelinePhase.GAP_ANALYZING:
            state.gap_report = dumped
            # Store the result object for transition logic
            state._last_gap_report = result  # type: ignore[attr-defined]
        elif phase == PipelinePhase.RE_HARVESTING:
            state.raw_harvest = dumped
        elif phase == PipelinePhase.LEARNING:
            state.knowledge_model = dumped
        elif phase == PipelinePhase.MAPPING:
            state.skill_draft = dumped
        elif phase == PipelinePhase.DOCUMENTING:
            state.setup_draft = dumped
        elif phase == PipelinePhase.VALIDATING:
            state.evaluation_results.append(dumped)
            state._last_eval_result = result  # type: ignore[attr-defined]
        elif phase == PipelinePhase.RE_PRODUCING:
            state.skill_draft = dumped
        elif phase == PipelinePhase.PACKAGING:
            state.package_path = dumped.get("package_path")
            state.verification_instructions = dumped.get("verification_instructions")

    def _next_phase(
        self, current: PipelinePhase, state: PipelineState
    ) -> PipelinePhase:
        """Determine the next phase based on current phase and state.

        Handles conditional transitions for gap analysis and validation loops.
        """
        entry = self.TRANSITION_TABLE.get(current)

        if entry is None:
            # Terminal phase or unknown -- no transition
            return current

        if entry != _CONDITIONAL:
            return PipelinePhase(entry)

        # Conditional transitions
        if current == PipelinePhase.GAP_ANALYZING:
            return self._resolve_gap_transition(state)
        if current == PipelinePhase.VALIDATING:
            return self._resolve_validation_transition(state)

        # Shouldn't reach here
        return PipelinePhase.FAILED

    def _resolve_gap_transition(self, state: PipelineState) -> PipelinePhase:
        """Resolve the gap analysis conditional transition.

        If gap report shows sufficient coverage -> LEARNING.
        If insufficient and under cap -> RE_HARVESTING (increment loop count).
        If insufficient and at cap -> LEARNING (force-proceed with warning).
        """
        gap_report = getattr(state, "_last_gap_report", None)

        if gap_report is None:
            # No gap report available; check the stored dict
            if state.gap_report and not state.gap_report.get("is_sufficient", True):
                is_sufficient = False
            else:
                is_sufficient = True
        elif isinstance(gap_report, GapReport):
            is_sufficient = gap_report.is_sufficient
        else:
            is_sufficient = True

        if is_sufficient:
            return PipelinePhase.LEARNING

        # Gap is insufficient
        if state.gap_loop_count < self.MAX_GAP_LOOPS:
            state.gap_loop_count += 1
            logger.info(
                "Gap analysis insufficient (loop %d/%d). Re-harvesting.",
                state.gap_loop_count,
                self.MAX_GAP_LOOPS,
            )
            return PipelinePhase.RE_HARVESTING

        # Cap reached -- force-proceed
        logger.warning(
            "Gap analysis still insufficient after %d loops. Force-proceeding to LEARNING.",
            self.MAX_GAP_LOOPS,
        )
        print(
            f"  [gap_analyzing] Insufficient after {self.MAX_GAP_LOOPS} loops."
            " Force-proceeding."
        )
        return PipelinePhase.LEARNING

    def _resolve_validation_transition(self, state: PipelineState) -> PipelinePhase:
        """Resolve the validation conditional transition.

        If evaluation passes -> PACKAGING.
        If fails and under cap -> RE_PRODUCING (increment loop count).
        If fails and at cap -> PACKAGING (force-proceed with warning).
        """
        eval_result = getattr(state, "_last_eval_result", None)

        if eval_result is None:
            # Check stored evaluation results
            if state.evaluation_results:
                last = state.evaluation_results[-1]
                overall_pass = last.get("overall_pass", True)
            else:
                overall_pass = True
        elif isinstance(eval_result, EvaluationResult):
            overall_pass = eval_result.overall_pass
        else:
            overall_pass = True

        if overall_pass:
            return PipelinePhase.PACKAGING

        # Validation failed
        if state.validation_loop_count < self.MAX_VALIDATION_LOOPS:
            state.validation_loop_count += 1
            logger.info(
                "Validation failed (loop %d/%d). Re-producing.",
                state.validation_loop_count,
                self.MAX_VALIDATION_LOOPS,
            )
            return PipelinePhase.RE_PRODUCING

        # Cap reached -- force-proceed
        logger.warning(
            "Validation still failing after %d loops. Force-proceeding to PACKAGING.",
            self.MAX_VALIDATION_LOOPS,
        )
        print(
            f"  [validating] Still failing after {self.MAX_VALIDATION_LOOPS} loops."
            " Force-proceeding."
        )
        return PipelinePhase.PACKAGING
