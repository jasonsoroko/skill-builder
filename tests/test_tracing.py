"""Tests for LangSmith tracing wrapper -- resilient tracing integration.

Per RES-02: LangSmith errors never block the pipeline.
"""

from __future__ import annotations

from unittest.mock import patch


class TestCreateTracedClient:
    """create_traced_client returns an Anthropic client with resilient tracing."""

    def test_returns_anthropic_client(self) -> None:
        """create_traced_client() returns an Anthropic client instance."""
        from skill_builder.tracing import create_traced_client

        client = create_traced_client()
        # Should be an Anthropic client (possibly wrapped)
        assert client is not None

    def test_works_without_langsmith(self) -> None:
        """create_traced_client() works even when LangSmith is unavailable."""
        from skill_builder.tracing import create_traced_client

        # Simulate LangSmith being unavailable by patching wrap_anthropic to fail
        with patch(
            "skill_builder.tracing._try_wrap_anthropic",
            side_effect=Exception("LangSmith unavailable"),
        ):
            client = create_traced_client()
            assert client is not None

    def test_suppresses_langsmith_exceptions(self, caplog: object) -> None:
        """create_traced_client() suppresses LangSmith errors and logs a warning."""
        from skill_builder.tracing import create_traced_client

        with patch(
            "skill_builder.tracing._try_wrap_anthropic",
            side_effect=RuntimeError("LangSmith crashed"),
        ):
            # Should not raise -- LangSmith errors are suppressed
            client = create_traced_client()
            assert client is not None


class TestTraceableAgent:
    """traceable_agent wraps functions with LangSmith tracing metadata."""

    def test_decorator_executes_function_normally(self) -> None:
        """traceable_agent decorator doesn't interfere with function execution."""
        from skill_builder.tracing import traceable_agent

        @traceable_agent(name="test_op", phase="harvest", agent_name="test_agent")
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    def test_decorator_works_without_langsmith(self) -> None:
        """traceable_agent works as a no-op when LangSmith is unavailable."""
        from skill_builder.tracing import traceable_agent

        @traceable_agent(name="test_op", phase="test", agent_name="stub")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(3, 4) == 7

    def test_decorator_with_iteration(self) -> None:
        """traceable_agent accepts iteration parameter for metadata."""
        from skill_builder.tracing import traceable_agent

        @traceable_agent(name="test_op", phase="validating", agent_name="validator", iteration=2)
        def validate() -> str:
            return "valid"

        assert validate() == "valid"


class TestTracingIntegration:
    """Test that conductor._run_phase applies traceable_agent to agent.run()."""

    def test_traceable_agent_applied_to_run(self, tmp_path) -> None:
        """Conductor wraps agent.run() with traceable_agent in _run_phase."""
        from unittest.mock import MagicMock, patch as mock_patch

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

        brief = SkillBrief(
            name="test-skill",
            description="A test skill",
            seed_urls=[{"url": "https://example.com", "type": "docs"}],
            tool_category="test",
            scope="testing",
            required_capabilities=["testing"],
            deploy_target="user",
        )
        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=1000.0)
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
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        # Mock traceable_agent to track calls
        mock_traceable = MagicMock()
        # Make it return the original function (passthrough)
        mock_traceable.return_value = lambda fn: fn

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.ORGANIZING,
            raw_harvest={"pages": [], "total_pages": 0},
        )

        with mock_patch("skill_builder.conductor.traceable_agent", mock_traceable):
            conductor._run_phase(PipelinePhase.ORGANIZING, state)

        mock_traceable.assert_called_once_with(
            name="organizer_run",
            phase="organizing",
            agent_name="organizer",
            iteration=0,
        )

    def test_iteration_uses_gap_loop_count_for_reharvesting(self, tmp_path) -> None:
        """RE_HARVESTING phase uses state.gap_loop_count as iteration."""
        from unittest.mock import MagicMock, patch as mock_patch

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

        brief = SkillBrief(
            name="test-skill",
            description="A test skill",
            seed_urls=[{"url": "https://example.com", "type": "docs"}],
            tool_category="test",
            scope="testing",
            required_capabilities=["testing"],
            deploy_target="user",
        )
        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=1000.0)
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
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        mock_traceable = MagicMock()
        mock_traceable.return_value = lambda fn: fn

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.RE_HARVESTING,
            gap_loop_count=2,
        )

        with mock_patch("skill_builder.conductor.traceable_agent", mock_traceable):
            conductor._run_phase(PipelinePhase.RE_HARVESTING, state)

        mock_traceable.assert_called_once_with(
            name="harvest_run",
            phase="re_harvesting",
            agent_name="harvest",
            iteration=2,
        )

    def test_iteration_uses_validation_loop_count_for_validating(self, tmp_path) -> None:
        """VALIDATING phase uses state.validation_loop_count as iteration."""
        from unittest.mock import MagicMock, patch as mock_patch

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

        brief = SkillBrief(
            name="test-skill",
            description="A test skill",
            seed_urls=[{"url": "https://example.com", "type": "docs"}],
            tool_category="test",
            scope="testing",
            required_capabilities=["testing"],
            deploy_target="user",
        )
        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=1000.0)
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
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        mock_traceable = MagicMock()
        mock_traceable.return_value = lambda fn: fn

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.VALIDATING,
            skill_draft={"content": "# Skill", "line_count": 1, "has_frontmatter": False},
            setup_draft={"content": "# Setup", "has_prerequisites": True, "has_quick_start": True},
            knowledge_model={"canonical_use_cases": [], "dependencies": []},
            validation_loop_count=1,
        )

        with mock_patch("skill_builder.conductor.traceable_agent", mock_traceable):
            conductor._run_phase(PipelinePhase.VALIDATING, state)

        mock_traceable.assert_called_once_with(
            name="validator_run",
            phase="validating",
            agent_name="validator",
            iteration=1,
        )

    def test_normal_phase_gets_iteration_zero(self, tmp_path) -> None:
        """Non-loop phases (e.g. INTAKE) get iteration=0."""
        from unittest.mock import MagicMock, patch as mock_patch

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

        brief = SkillBrief(
            name="test-skill",
            description="A test skill",
            seed_urls=[{"url": "https://example.com", "type": "docs"}],
            tool_category="test",
            scope="testing",
            required_capabilities=["testing"],
            deploy_target="user",
        )
        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=1000.0)
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
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        mock_traceable = MagicMock()
        mock_traceable.return_value = lambda fn: fn

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.INTAKE,
        )

        with mock_patch("skill_builder.conductor.traceable_agent", mock_traceable):
            conductor._run_phase(PipelinePhase.INTAKE, state)

        mock_traceable.assert_called_once_with(
            name="intake_run",
            phase="intake",
            agent_name="intake",
            iteration=0,
        )

    def test_traced_run_returns_correct_result(self, tmp_path) -> None:
        """The traced agent.run() wrapper returns the correct result."""
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
        from skill_builder.models.synthesis import CategorizedResearch

        brief = SkillBrief(
            name="test-skill",
            description="A test skill",
            seed_urls=[{"url": "https://example.com", "type": "docs"}],
            tool_category="test",
            scope="testing",
            required_capabilities=["testing"],
            deploy_target="user",
        )
        store = CheckpointStore(tmp_path / "state")
        budget = TokenBudget(budget_usd=1000.0)
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
        conductor = Conductor(brief=brief, store=store, budget=budget, agents=agents)

        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.ORGANIZING,
            raw_harvest={"pages": [], "total_pages": 0},
        )

        # Run without patching traceable_agent -- it falls through to no-op
        conductor._run_phase(PipelinePhase.ORGANIZING, state)

        # Result should be stored in state
        assert state.categorized_research is not None


class TestStubAgents:
    """Stub agents return valid Pydantic model instances for each pipeline phase."""

    def test_stub_intake_agent(self) -> None:
        """StubIntakeAgent returns a validated SkillBrief (pass-through)."""
        from skill_builder.agents.stubs import StubIntakeAgent
        from skill_builder.models.brief import SkillBrief

        agent = StubIntakeAgent()
        result = agent.run()
        assert isinstance(result, SkillBrief)

    def test_stub_harvest_agent(self) -> None:
        """StubHarvestAgent returns a HarvestResult with pages."""
        from skill_builder.agents.stubs import StubHarvestAgent
        from skill_builder.models.harvest import HarvestResult

        agent = StubHarvestAgent()
        result = agent.run()
        assert isinstance(result, HarvestResult)
        assert len(result.pages) == 3

    def test_stub_organizer_agent(self) -> None:
        """StubOrganizerAgent returns a CategorizedResearch with categories."""
        from skill_builder.agents.stubs import StubOrganizerAgent
        from skill_builder.models.synthesis import CategorizedResearch

        agent = StubOrganizerAgent()
        result = agent.run()
        assert isinstance(result, CategorizedResearch)
        assert len(result.categories) == 3

    def test_stub_gap_analyzer_sufficient(self) -> None:
        """StubGapAnalyzerAgent returns is_sufficient=True by default."""
        from skill_builder.agents.stubs import StubGapAnalyzerAgent
        from skill_builder.models.synthesis import GapReport

        agent = StubGapAnalyzerAgent()
        result = agent.run()
        assert isinstance(result, GapReport)
        assert result.is_sufficient is True

    def test_stub_gap_analyzer_insufficient(self) -> None:
        """StubGapAnalyzerAgent returns is_sufficient=False when force_insufficient=True."""
        from skill_builder.agents.stubs import StubGapAnalyzerAgent
        from skill_builder.models.synthesis import GapReport

        agent = StubGapAnalyzerAgent()
        result = agent.run(force_insufficient=True)
        assert isinstance(result, GapReport)
        assert result.is_sufficient is False
        assert len(result.identified_gaps) > 0
        assert len(result.recommended_search_queries) > 0

    def test_stub_learner_agent(self) -> None:
        """StubLearnerAgent returns a KnowledgeModel with fixture data."""
        from skill_builder.agents.stubs import StubLearnerAgent
        from skill_builder.models.synthesis import KnowledgeModel

        agent = StubLearnerAgent()
        result = agent.run()
        assert isinstance(result, KnowledgeModel)
        assert len(result.canonical_use_cases) > 0

    def test_stub_mapper_agent(self) -> None:
        """StubMapperAgent returns a SkillDraft with content."""
        from skill_builder.agents.stubs import StubMapperAgent
        from skill_builder.models.production import SkillDraft

        agent = StubMapperAgent()
        result = agent.run()
        assert isinstance(result, SkillDraft)
        assert len(result.content) > 0

    def test_stub_documenter_agent(self) -> None:
        """StubDocumenterAgent returns a SetupDraft with content."""
        from skill_builder.agents.stubs import StubDocumenterAgent
        from skill_builder.models.production import SetupDraft

        agent = StubDocumenterAgent()
        result = agent.run()
        assert isinstance(result, SetupDraft)
        assert result.has_prerequisites is True
        assert result.has_quick_start is True

    def test_stub_validator_pass(self) -> None:
        """StubValidatorAgent returns overall_pass=True by default."""
        from skill_builder.agents.stubs import StubValidatorAgent
        from skill_builder.models.evaluation import EvaluationResult

        agent = StubValidatorAgent()
        result = agent.run()
        assert isinstance(result, EvaluationResult)
        assert result.overall_pass is True

    def test_stub_validator_fail(self) -> None:
        """StubValidatorAgent returns overall_pass=False when force_fail=True."""
        from skill_builder.agents.stubs import StubValidatorAgent
        from skill_builder.models.evaluation import EvaluationResult

        agent = StubValidatorAgent()
        result = agent.run(force_fail=True)
        assert isinstance(result, EvaluationResult)
        assert result.overall_pass is False
        # Should have low scores
        assert all(d.score < 7 for d in result.dimensions)

    def test_stub_packager_agent(self) -> None:
        """StubPackagerAgent returns a dict with package_path."""
        from skill_builder.agents.stubs import StubPackagerAgent

        agent = StubPackagerAgent()
        result = agent.run()
        assert isinstance(result, dict)
        assert "package_path" in result
        assert isinstance(result["package_path"], str)
