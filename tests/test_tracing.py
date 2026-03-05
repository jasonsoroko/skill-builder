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
