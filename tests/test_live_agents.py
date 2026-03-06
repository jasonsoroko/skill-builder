"""Layer 3: Single-agent integration tests with fixture chaining.

Each test runs one real agent against real APIs with minimal input.
Tests run in pipeline order; each saves output to tests/fixtures/live/
so downstream tests can consume it without re-running upstream agents.

Total cost: ~$1.50. Run with: pytest -m live tests/test_live_agents.py --tb=short -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from skill_builder.models.brief import SkillBrief
from skill_builder.models.evaluation import EvaluationResult
from skill_builder.models.harvest import HarvestResult
from skill_builder.models.production import SetupDraft, SkillDraft
from skill_builder.models.state import PipelineState
from skill_builder.models.synthesis import CategorizedResearch, GapReport, KnowledgeModel

pytestmark = [pytest.mark.live, pytest.mark.timeout(180)]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "live"

# Minimal brief — 1 seed URL, 2 capabilities, max_pages=5
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


def _skip_if_no_key(env_var: str) -> None:
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


def _skip_if_no_anthropic_and_apis() -> None:
    """Skip if missing any key needed for agent tests."""
    for key in ("ANTHROPIC_API_KEY", "FIRECRAWL_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY"):
        _skip_if_no_key(key)


def _save_fixture(name: str, data: dict) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))


def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Fixture {name}.json not found — run upstream test first")
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def brief() -> SkillBrief:
    return SkillBrief(**_BRIEF_DICT)


class TestLiveAgents:
    """Run each agent in pipeline order with real APIs and fixture chaining."""

    def test_01_harvest_agent(self, brief: SkillBrief) -> None:
        """HarvestAgent produces HarvestResult with real pages."""
        _skip_if_no_anthropic_and_apis()
        from skill_builder.agents.harvest import HarvestAgent

        agent = HarvestAgent()
        state = PipelineState(brief_name="exa-search-test")
        result = agent.run(brief=brief, state=state)

        assert isinstance(result, HarvestResult)
        assert result.total_pages > 0
        assert len(result.pages) > 0
        for page in result.pages:
            assert page.content
        _save_fixture("harvest", result.model_dump())

    def test_02_organizer_agent(self, brief: SkillBrief) -> None:
        """OrganizerAgent produces CategorizedResearch from harvest fixture."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.organizer import OrganizerAgent

        harvest = _load_fixture("harvest")
        agent = OrganizerAgent()
        result = agent.run(raw_harvest=harvest, brief=brief)

        assert isinstance(result, CategorizedResearch)
        assert len(result.categories) > 0
        assert result.source_count > 0
        _save_fixture("organizer", result.model_dump())

    def test_03_gap_analyzer_agent(self, brief: SkillBrief) -> None:
        """GapAnalyzerAgent produces GapReport from organizer fixture."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.gap_analyzer import GapAnalyzerAgent

        org = _load_fixture("organizer")
        agent = GapAnalyzerAgent()
        result = agent.run(categorized_research=org, brief=brief)

        assert isinstance(result, GapReport)
        assert isinstance(result.is_sufficient, bool)
        if not result.is_sufficient:
            assert len(result.identified_gaps) > 0
        _save_fixture("gap_analyzer", result.model_dump())

    def test_04_learner_agent(self, brief: SkillBrief) -> None:
        """LearnerAgent produces KnowledgeModel from organizer + gap fixtures."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.learner import LearnerAgent

        org = _load_fixture("organizer")
        gap = _load_fixture("gap_analyzer")
        agent = LearnerAgent()
        result = agent.run(categorized_research=org, gap_report=gap, brief=brief)

        assert isinstance(result, KnowledgeModel)
        assert len(result.canonical_use_cases) > 0
        assert len(result.common_gotchas) > 0
        assert result.minimum_viable_example
        _save_fixture("learner", result.model_dump())

    def test_05_mapper_agent(self, brief: SkillBrief) -> None:
        """MapperAgent produces SkillDraft from learner fixture."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.mapper import MapperAgent

        km = _load_fixture("learner")
        agent = MapperAgent()
        result = agent.run(knowledge_model=km, brief=brief)

        assert isinstance(result, SkillDraft)
        assert result.has_frontmatter is True
        assert result.line_count > 0
        assert result.line_count <= 500
        assert result.content.startswith("---")
        _save_fixture("mapper", result.model_dump())

    def test_06_documenter_agent(self, brief: SkillBrief) -> None:
        """DocumenterAgent produces SetupDraft from learner fixture."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.documenter import DocumenterAgent

        km = _load_fixture("learner")
        agent = DocumenterAgent()
        result = agent.run(knowledge_model=km, brief=brief)

        assert isinstance(result, SetupDraft)
        assert result.has_prerequisites is True
        assert result.has_quick_start is True
        assert "Prerequisites" in result.content or "prerequisites" in result.content.lower()
        _save_fixture("documenter", result.model_dump())

    def test_07_validator_agent(self, brief: SkillBrief) -> None:
        """ValidatorAgent produces EvaluationResult from mapper + learner + organizer fixtures."""
        _skip_if_no_key("ANTHROPIC_API_KEY")
        from skill_builder.agents.validator import ValidatorAgent

        skill = _load_fixture("mapper")
        km = _load_fixture("learner")
        org = _load_fixture("organizer")
        agent = ValidatorAgent()
        result = agent.run(
            skill_draft=skill,
            setup_draft=_load_fixture("documenter"),
            knowledge_model=km,
            brief=brief,
            categorized_research=org,
            iteration=1,
        )

        assert isinstance(result, EvaluationResult)
        # Either 2 dims (heuristic fail-fast) or 5 dims (full evaluation)
        assert len(result.dimensions) in (2, 5)
        for dim in result.dimensions:
            assert 1 <= dim.score <= 10
            assert isinstance(dim.passed, bool)
        assert result.overall_pass == all(d.passed for d in result.dimensions)
        _save_fixture("validator", result.model_dump())

    def test_08_packager_agent(self, brief: SkillBrief, tmp_path: Path) -> None:
        """PackagerAgent assembles output directory from mapper + documenter fixtures."""
        from skill_builder.agents.packager import PackagerAgent

        skill = _load_fixture("mapper")
        setup = _load_fixture("documenter")

        # Override deploy_target to package so output goes to tmp_path
        test_brief = brief.model_copy(update={"deploy_target": "package"})

        agent = PackagerAgent()
        # Monkey-patch output path to tmp_path to avoid polluting real dirs
        import skill_builder.agents.packager as pkg_mod
        original_resolve = pkg_mod._resolve_deploy_path
        pkg_mod._resolve_deploy_path = lambda target, name: tmp_path / name

        try:
            result = agent.run(skill_draft=skill, setup_draft=setup, brief=test_brief)
        finally:
            pkg_mod._resolve_deploy_path = original_resolve

        assert "package_path" in result
        assert "verification_instructions" in result
        out = Path(result["package_path"])
        assert (out / "SKILL.md").exists()
        assert (out / "SETUP.md").exists()
        assert (out / "LICENSE.txt").exists()
        for subdir in ("references", "scripts", "assets"):
            assert (out / subdir).is_dir()
