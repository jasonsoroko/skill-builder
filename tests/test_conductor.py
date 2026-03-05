"""Tests for the conductor state machine.

Covers:
- Happy path: all phase transitions with stub agents
- Gap loop: insufficient gap analysis triggers re-harvest (max 2 iterations)
- Validation loop: failing validation triggers re-production (max 2 iterations)
- Checkpoint persistence: save() called after each phase transition
- Resume from checkpoint: conductor continues from a saved state
- Budget exceeded: conductor halts after current agent when budget exceeded
- FAILED state: conductor transitions to FAILED on unexpected exception
- Every non-terminal phase has success and failure transitions
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

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
from skill_builder.budget import TokenBudget
from skill_builder.checkpoint import CheckpointStore
from skill_builder.conductor import Conductor
from skill_builder.models.brief import SkillBrief
from skill_builder.models.state import PipelinePhase, PipelineState


@pytest.fixture
def brief() -> SkillBrief:
    """Return a minimal valid SkillBrief for testing."""
    return SkillBrief(
        name="test-skill",
        description="A test skill",
        seed_urls=[{"url": "https://example.com", "type": "docs"}],
        tool_category="test",
        scope="testing",
        required_capabilities=["testing"],
        deploy_target="user",
    )


@pytest.fixture
def store(tmp_path: Path) -> CheckpointStore:
    """Return a CheckpointStore using a temp directory."""
    return CheckpointStore(tmp_path / "state")


@pytest.fixture
def budget() -> TokenBudget:
    """Return a TokenBudget with high limit (won't exceed)."""
    return TokenBudget(budget_usd=1000.0)


@pytest.fixture
def stub_agents() -> dict:
    """Return a full set of stub agents for testing."""
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


@pytest.fixture
def conductor(
    brief: SkillBrief, store: CheckpointStore, budget: TokenBudget, stub_agents: dict
) -> Conductor:
    """Return a Conductor wired with stub agents."""
    return Conductor(brief=brief, store=store, budget=budget, agents=stub_agents)


class TestHappyPath:
    """Test that the conductor transitions through all phases in order."""

    def test_full_pipeline_reaches_complete(
        self, conductor: Conductor
    ) -> None:
        """Conductor transitions through all phases to COMPLETE with stub agents."""
        result = conductor.run()
        assert result.phase == PipelinePhase.COMPLETE

    def test_full_pipeline_visits_all_phases(
        self, conductor: Conductor
    ) -> None:
        """Conductor visits every expected phase in order on happy path."""
        result = conductor.run()
        assert result.phase == PipelinePhase.COMPLETE
        # gap_loop_count should be 0 (no re-harvest needed)
        assert result.gap_loop_count == 0
        # validation_loop_count should be 0 (validation passed first time)
        assert result.validation_loop_count == 0


class TestGapLoop:
    """Test gap analysis feedback loop (conductor routes failure to re-harvest)."""

    def test_gap_loop_triggers_reharvest(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """When gap analyzer returns insufficient, conductor re-harvests then retries."""
        # Create a gap analyzer that fails first time, succeeds second time
        call_count = 0
        original_gap = StubGapAnalyzerAgent()

        class CountingGapAnalyzer:
            def run(self, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return original_gap.run(force_insufficient=True)
                return original_gap.run(force_insufficient=False)

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": CountingGapAnalyzer(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run()

        assert result.phase == PipelinePhase.COMPLETE
        assert result.gap_loop_count == 1
        assert call_count == 2  # called twice: fail then pass

    def test_gap_loop_caps_at_two(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """After 2 gap loops, conductor force-proceeds to LEARNING."""
        # Gap analyzer always returns insufficient
        agents = {
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
        # Make the gap analyzer always fail
        original_run = agents["gap_analyzer"].run
        agents["gap_analyzer"].run = lambda **kwargs: original_run(force_insufficient=True)

        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run()

        # Should still complete (force-proceed after cap)
        assert result.phase == PipelinePhase.COMPLETE
        assert result.gap_loop_count == 2  # capped at 2


class TestValidationLoop:
    """Test validation feedback loop (conductor routes failure to re-production)."""

    def test_validation_loop_triggers_reproduce(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """When validator fails, conductor re-produces then retries."""
        call_count = 0
        original_validator = StubValidatorAgent()

        class CountingValidator:
            def run(self, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return original_validator.run(force_fail=True, iteration=call_count)
                return original_validator.run(force_fail=False, iteration=call_count)

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": CountingValidator(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run()

        assert result.phase == PipelinePhase.COMPLETE
        assert result.validation_loop_count == 1
        assert call_count == 2

    def test_validation_loop_caps_at_two(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """After 2 validation loops, conductor force-proceeds to PACKAGING."""
        original_validator = StubValidatorAgent()
        call_count = 0

        class AlwaysFailValidator:
            def run(self, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_validator.run(force_fail=True, iteration=call_count)

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": AlwaysFailValidator(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run()

        assert result.phase == PipelinePhase.COMPLETE
        assert result.validation_loop_count == 2


class TestCheckpointPersistence:
    """Test that checkpoint is saved after each phase transition."""

    def test_save_called_after_each_transition(
        self, brief: SkillBrief, budget: TokenBudget, tmp_path: Path, stub_agents: dict
    ) -> None:
        """CheckpointStore.save() is called after each phase transition."""
        store = CheckpointStore(tmp_path / "state")
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=stub_agents)

        with patch.object(store, "save", wraps=store.save) as mock_save:
            conductor.run()

        # There should be at least as many save calls as phase transitions
        # Happy path: INITIALIZED -> INTAKE -> HARVESTING -> ORGANIZING ->
        # GAP_ANALYZING -> LEARNING -> MAPPING -> DOCUMENTING -> VALIDATING ->
        # PACKAGING -> COMPLETE = 10 transitions
        assert mock_save.call_count >= 10

    def test_checkpoint_file_exists_after_run(
        self, conductor: Conductor, store: CheckpointStore
    ) -> None:
        """After a run, the checkpoint file should exist on disk."""
        conductor.run()
        assert store.exists("test-skill")


class TestResumeFromCheckpoint:
    """Test that conductor can resume from a previously saved state."""

    def test_resume_from_organizing(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """Conductor resumes from ORGANIZING, skipping INTAKE, HARVESTING, and ORGANIZING.

        When the checkpoint says phase=ORGANIZING, it means the organizer agent
        already completed (checkpoint is saved AFTER the agent runs). The conductor
        resumes from the NEXT phase (GAP_ANALYZING).
        """
        # Save state at ORGANIZING phase (already completed)
        saved_state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.ORGANIZING,
        )
        store.save(saved_state)

        # Track which agents are called
        called_agents: list[str] = []

        class TrackingIntake:
            def run(self, **kwargs):
                called_agents.append("intake")
                return StubIntakeAgent().run()

        class TrackingHarvest:
            def run(self, **kwargs):
                called_agents.append("harvest")
                return StubHarvestAgent().run()

        class TrackingOrganizer:
            def run(self, **kwargs):
                called_agents.append("organizer")
                return StubOrganizerAgent().run()

        class TrackingGapAnalyzer:
            def run(self, **kwargs):
                called_agents.append("gap_analyzer")
                return StubGapAnalyzerAgent().run()

        agents = {
            "intake": TrackingIntake(),
            "harvest": TrackingHarvest(),
            "organizer": TrackingOrganizer(),
            "gap_analyzer": TrackingGapAnalyzer(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }

        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run(state=saved_state)

        assert result.phase == PipelinePhase.COMPLETE
        # Intake, Harvest, and Organizer should NOT have been called (already past)
        assert "intake" not in called_agents
        assert "harvest" not in called_agents
        assert "organizer" not in called_agents
        # Gap analyzer should have been called (first phase after ORGANIZING)
        assert "gap_analyzer" in called_agents


class TestBudgetExceeded:
    """Test that conductor halts when budget is exceeded."""

    def test_budget_exceeded_halts_pipeline(
        self, brief: SkillBrief, store: CheckpointStore, stub_agents: dict
    ) -> None:
        """Conductor halts after current agent when budget is exceeded."""
        # Set a very low budget that will be exceeded immediately
        budget = TokenBudget(budget_usd=0.0)
        budget.total_cost_usd = 1.0  # Already exceeded

        conductor = Conductor(brief=brief, store=store, budget=budget, agents=stub_agents)
        result = conductor.run()

        # Pipeline should NOT reach COMPLETE -- it halted due to budget
        assert result.phase != PipelinePhase.COMPLETE
        # State should be saved (checkpointed)
        assert store.exists("test-skill")

    def test_budget_exceeded_saves_state(
        self, brief: SkillBrief, store: CheckpointStore, stub_agents: dict
    ) -> None:
        """When budget is exceeded, the state is saved for later resume."""
        budget = TokenBudget(budget_usd=0.0)
        budget.total_cost_usd = 1.0

        conductor = Conductor(brief=brief, store=store, budget=budget, agents=stub_agents)
        result = conductor.run()

        # Load the saved state
        loaded = store.load("test-skill")
        assert loaded is not None
        assert loaded.phase == result.phase


class TestFailedState:
    """Test that conductor transitions to FAILED on unexpected exception."""

    def test_agent_exception_transitions_to_failed(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """When an agent raises, conductor transitions to FAILED."""

        class CrashingHarvest:
            def run(self, **kwargs):
                raise RuntimeError("Simulated harvest failure")

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": CrashingHarvest(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        result = conductor.run()

        assert result.phase == PipelinePhase.FAILED
        assert result.error is not None
        assert "Simulated harvest failure" in result.error

    def test_failed_state_is_checkpointed(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """FAILED state is saved to checkpoint."""

        class CrashingOrganizer:
            def run(self, **kwargs):
                raise ValueError("Organizer crashed")

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": CrashingOrganizer(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)
        conductor.run()

        loaded = store.load("test-skill")
        assert loaded is not None
        assert loaded.phase == PipelinePhase.FAILED
        assert loaded.error is not None


class TestTransitionCompleteness:
    """Test that every non-terminal phase has both success and failure paths."""

    def test_all_phases_have_transitions(self) -> None:
        """Every non-terminal phase must be in the conductor's transition logic."""
        terminal_phases = {PipelinePhase.COMPLETE, PipelinePhase.FAILED}
        non_terminal = {p for p in PipelinePhase if p not in terminal_phases}

        # The conductor must know how to handle every non-terminal phase
        # We check this by verifying TRANSITION_TABLE covers them
        from skill_builder.conductor import Conductor

        for phase in non_terminal:
            assert phase in Conductor.TRANSITION_TABLE, (
                f"Phase {phase} has no entry in TRANSITION_TABLE"
            )


class TestFocusedKwargsDispatch:
    """Test that _run_phase passes correct kwargs to agents per phase."""

    def test_harvesting_passes_brief_and_state(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """HARVESTING phase passes brief and state to agent."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubHarvestAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": mock_agent,
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.HARVESTING,
        )
        conductor._run_phase(PipelinePhase.HARVESTING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "brief" in call_kwargs
        assert "state" in call_kwargs
        assert call_kwargs["brief"] is brief
        assert call_kwargs["state"] is state

    def test_organizing_passes_raw_harvest_and_brief(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """ORGANIZING phase passes raw_harvest and brief to agent."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubOrganizerAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": mock_agent,
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        raw_harvest = {"pages": [], "total_pages": 0}
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.ORGANIZING,
            raw_harvest=raw_harvest,
        )
        conductor._run_phase(PipelinePhase.ORGANIZING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "raw_harvest" in call_kwargs
        assert "brief" in call_kwargs
        assert call_kwargs["raw_harvest"] == raw_harvest

    def test_gap_analyzing_passes_categorized_research_and_brief(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """GAP_ANALYZING phase passes categorized_research, brief, and harvest_warnings."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubGapAnalyzerAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": mock_agent,
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        categorized = {"categories": [], "source_count": 0}
        raw_harvest = {
            "pages": [],
            "total_pages": 0,
            "warnings": ["Version mismatch"],
        }
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.GAP_ANALYZING,
            categorized_research=categorized,
            raw_harvest=raw_harvest,
        )
        conductor._run_phase(PipelinePhase.GAP_ANALYZING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "categorized_research" in call_kwargs
        assert "brief" in call_kwargs
        assert "harvest_warnings" in call_kwargs
        assert call_kwargs["harvest_warnings"] == ["Version mismatch"]

    def test_learning_passes_categorized_research_gap_report_and_brief(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """LEARNING phase passes categorized_research, gap_report, and brief."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubLearnerAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": mock_agent,
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        categorized = {"categories": [], "source_count": 0}
        gap_report = {"is_sufficient": True, "identified_gaps": []}
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.LEARNING,
            categorized_research=categorized,
            gap_report=gap_report,
        )
        conductor._run_phase(PipelinePhase.LEARNING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "categorized_research" in call_kwargs
        assert "gap_report" in call_kwargs
        assert "brief" in call_kwargs
        assert call_kwargs["categorized_research"] == categorized
        assert call_kwargs["gap_report"] == gap_report

    def test_validating_passes_categorized_research_and_iteration(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """VALIDATING phase passes categorized_research and iteration to agent."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubValidatorAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": StubMapperAgent(),
            "documenter": StubDocumenterAgent(),
            "validator": mock_agent,
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        skill_draft = {"content": "# Skill", "line_count": 1, "has_frontmatter": False}
        setup_draft = {"content": "# Setup", "has_prerequisites": True, "has_quick_start": True}
        knowledge_model = {"canonical_use_cases": [], "dependencies": []}
        categorized = {"categories": [], "source_count": 0}

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.VALIDATING,
            skill_draft=skill_draft,
            setup_draft=setup_draft,
            knowledge_model=knowledge_model,
            categorized_research=categorized,
            validation_loop_count=0,
        )
        conductor._run_phase(PipelinePhase.VALIDATING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "skill_draft" in call_kwargs
        assert "setup_draft" in call_kwargs
        assert "knowledge_model" in call_kwargs
        assert "brief" in call_kwargs
        assert "categorized_research" in call_kwargs
        assert call_kwargs["categorized_research"] == categorized
        assert "iteration" in call_kwargs
        assert call_kwargs["iteration"] == 1  # validation_loop_count 0 + 1

    def test_re_producing_passes_failed_dimensions(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """RE_PRODUCING phase passes failed_dimensions from last evaluation."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubMapperAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": mock_agent,
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        knowledge_model = {"canonical_use_cases": [], "dependencies": []}
        eval_results = [
            {
                "dimensions": [
                    {"name": "compactness", "score": 10, "feedback": "OK", "passed": True},
                    {"name": "api_accuracy", "score": 5, "feedback": "Wrong endpoints", "passed": False},
                ],
                "overall_pass": False,
                "iteration": 1,
            }
        ]

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.RE_PRODUCING,
            knowledge_model=knowledge_model,
            evaluation_results=eval_results,
        )
        conductor._run_phase(PipelinePhase.RE_PRODUCING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "knowledge_model" in call_kwargs
        assert "brief" in call_kwargs
        assert "failed_dimensions" in call_kwargs
        # Only the failed dimension should be passed
        assert len(call_kwargs["failed_dimensions"]) == 1
        assert call_kwargs["failed_dimensions"][0]["name"] == "api_accuracy"

    def test_re_producing_omits_failed_dimensions_when_no_evals(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget
    ) -> None:
        """RE_PRODUCING kwargs omit failed_dimensions when no evaluation results exist."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_agent.run.return_value = StubMapperAgent().run()

        agents = {
            "intake": StubIntakeAgent(),
            "harvest": StubHarvestAgent(),
            "organizer": StubOrganizerAgent(),
            "gap_analyzer": StubGapAnalyzerAgent(),
            "learner": StubLearnerAgent(),
            "mapper": mock_agent,
            "documenter": StubDocumenterAgent(),
            "validator": StubValidatorAgent(),
            "packager": StubPackagerAgent(),
        }
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        knowledge_model = {"canonical_use_cases": [], "dependencies": []}

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.RE_PRODUCING,
            knowledge_model=knowledge_model,
        )
        conductor._run_phase(PipelinePhase.RE_PRODUCING, state)

        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert "knowledge_model" in call_kwargs
        assert "brief" in call_kwargs
        assert "failed_dimensions" not in call_kwargs


class TestProgressIntegration:
    """Test that Conductor integrates with PipelineProgress."""

    def test_conductor_accepts_progress_none(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget, stub_agents: dict
    ) -> None:
        """Conductor works fine with progress=None (default)."""
        conductor = Conductor(
            brief=brief, store=store, budget=budget, agents=stub_agents, progress=None
        )
        result = conductor.run()
        assert result.phase == PipelinePhase.COMPLETE

    def test_conductor_calls_progress_phase_start(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget, stub_agents: dict
    ) -> None:
        """When progress is provided, phase_start is called for each phase."""
        from unittest.mock import MagicMock

        mock_progress = MagicMock()
        mock_progress.verbose = False

        conductor = Conductor(
            brief=brief, store=store, budget=budget,
            agents=stub_agents, progress=mock_progress
        )
        conductor.run()

        assert mock_progress.phase_start.call_count >= 9  # at least 9 phases
        assert mock_progress.phase_complete.call_count >= 9

    def test_conductor_calls_eval_score_after_validation(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget, stub_agents: dict
    ) -> None:
        """After VALIDATING phase, progress.eval_score is called for each dimension."""
        from unittest.mock import MagicMock

        mock_progress = MagicMock()
        mock_progress.verbose = False

        conductor = Conductor(
            brief=brief, store=store, budget=budget,
            agents=stub_agents, progress=mock_progress
        )
        conductor.run()

        # StubValidatorAgent returns 3 dimensions
        assert mock_progress.eval_score.call_count >= 3

    def test_conductor_calls_budget_display_when_verbose(
        self, brief: SkillBrief, store: CheckpointStore, budget: TokenBudget, stub_agents: dict
    ) -> None:
        """When progress.verbose is True, budget_display is called at phase boundaries."""
        from unittest.mock import MagicMock

        mock_progress = MagicMock()
        mock_progress.verbose = True

        conductor = Conductor(
            brief=brief, store=store, budget=budget,
            agents=stub_agents, progress=mock_progress
        )
        conductor.run()

        assert mock_progress.budget_display.call_count >= 1


class TestDefaultAgents:
    """Test that _default_agents returns correct agent types."""

    def test_real_agents_for_phase2(self) -> None:
        """_default_agents uses real agents for harvest, organizer, gap_analyzer, learner."""
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent
        from skill_builder.agents.harvest import HarvestAgent
        from skill_builder.agents.learner import LearnerAgent
        from skill_builder.agents.organizer import OrganizerAgent
        from skill_builder.conductor import _default_agents

        agents = _default_agents()

        assert isinstance(agents["harvest"], HarvestAgent)
        assert isinstance(agents["organizer"], OrganizerAgent)
        assert isinstance(agents["gap_analyzer"], GapAnalyzerAgent)
        assert isinstance(agents["learner"], LearnerAgent)

    def test_real_agents_for_phase3(self) -> None:
        """_default_agents uses real agents for mapper, documenter, validator."""
        from skill_builder.agents.documenter import DocumenterAgent
        from skill_builder.agents.mapper import MapperAgent
        from skill_builder.agents.validator import ValidatorAgent
        from skill_builder.conductor import _default_agents

        agents = _default_agents()

        assert isinstance(agents["mapper"], MapperAgent)
        assert isinstance(agents["documenter"], DocumenterAgent)
        assert isinstance(agents["validator"], ValidatorAgent)

    def test_real_packager_agent(self) -> None:
        """_default_agents uses real PackagerAgent."""
        from skill_builder.agents.packager import PackagerAgent
        from skill_builder.conductor import _default_agents

        agents = _default_agents()

        assert isinstance(agents["packager"], PackagerAgent)

    def test_stub_agents_for_remaining(self) -> None:
        """_default_agents uses stubs for intake (not yet implemented)."""
        from skill_builder.conductor import _default_agents

        agents = _default_agents()

        assert isinstance(agents["intake"], StubIntakeAgent)
