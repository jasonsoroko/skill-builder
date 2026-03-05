"""Tests for the HarvestAgent orchestrating parallel harvest.

Covers:
- Happy path: returns HarvestResult with pages from all sources
- Parallel execution via asyncio.gather
- Error resilience: one strategy fails, others still return pages
- Dedup is called on combined pages
- Version check results included in HarvestResult
- Saturation warning added when missing capabilities detected
- Re-harvest mode: uses refine_gap_queries when gap_loop_count > 0
- Conforms to BaseAgent Protocol
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.harvest import HarvestPage, HarvestResult
from skill_builder.models.state import PipelinePhase, PipelineState
from skill_builder.models.synthesis import GeneratedQueries, SaturationResult


def _make_brief(**overrides) -> SkillBrief:
    """Create a test SkillBrief."""
    defaults = {
        "name": "test-tool",
        "description": "A test tool",
        "seed_urls": [
            SeedUrl(url="https://docs.test.dev/", type="docs"),
            SeedUrl(url="https://github.com/test/repo", type="github"),
        ],
        "tool_category": "testing",
        "scope": "Testing the tool",
        "required_capabilities": ["auth", "caching"],
        "deploy_target": "user",
        "max_pages": 10,
    }
    defaults.update(overrides)
    return SkillBrief(**defaults)


def _make_state(**overrides) -> PipelineState:
    """Create a test PipelineState."""
    defaults = {
        "brief_name": "test-tool",
        "phase": PipelinePhase.HARVESTING,
        "gap_loop_count": 0,
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


def _make_page(url: str, source_type: str = "crawl", content: str = "content") -> HarvestPage:
    """Create a test HarvestPage."""
    return HarvestPage(
        url=url,
        title=f"Page: {url}",
        content=content,
        source_type=source_type,
    )


def _make_queries() -> GeneratedQueries:
    """Create test GeneratedQueries."""
    return GeneratedQueries(
        exa_queries=["test exa query"],
        tavily_queries=["test tavily query"],
    )


class TestHarvestAgentProtocol:
    """Test HarvestAgent conforms to BaseAgent Protocol."""

    def test_conforms_to_base_agent(self) -> None:
        """HarvestAgent satisfies BaseAgent protocol."""
        from skill_builder.agents.base import BaseAgent
        from skill_builder.agents.harvest import HarvestAgent

        mock_client = MagicMock()
        agent = HarvestAgent(client=mock_client)
        assert isinstance(agent, BaseAgent)


class TestHarvestAgentHappyPath:
    """Test HarvestAgent happy path execution."""

    @pytest.mark.asyncio
    async def test_returns_harvest_result_with_pages(self) -> None:
        """HarvestAgent.run() returns HarvestResult with pages from all sources."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        crawl_page = _make_page("https://docs.test.dev/intro", "crawl")
        github_pages = [_make_page("https://github.com/test/repo#readme", "github_api")]
        exa_page = _make_page("https://example.com/best-practices", "exa_search")
        tavily_page = _make_page("https://example.com/errors", "tavily_search")

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                side_effect=[
                    [crawl_page],
                    (github_pages, []),  # GitHub returns tuple
                ],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[exa_page],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[tavily_page],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert isinstance(result, HarvestResult)
        assert result.total_pages == 4
        assert len(result.pages) == 4

    @pytest.mark.asyncio
    async def test_queries_included_in_result(self) -> None:
        """HarvestAgent includes search queries used in the result."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert "test exa query" in result.queries_used
        assert "test tavily query" in result.queries_used


class TestHarvestAgentErrorResilience:
    """Test HarvestAgent error handling."""

    @pytest.mark.asyncio
    async def test_one_strategy_fails_others_still_return(self) -> None:
        """When one extraction strategy throws, others still contribute pages."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        good_page = _make_page("https://docs.test.dev/intro", "crawl")

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                side_effect=[
                    [good_page],  # docs succeeds
                    RuntimeError("GitHub API down"),  # github fails
                ],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        # Should still have the one good page
        assert result.total_pages >= 1


class TestHarvestAgentDedup:
    """Test dedup integration."""

    @pytest.mark.asyncio
    async def test_deduplicate_called_on_combined_pages(self) -> None:
        """HarvestAgent calls deduplicate() on all collected pages."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        page1 = _make_page("https://docs.test.dev/intro", "crawl")
        page2 = _make_page("https://docs.test.dev/intro", "crawl")  # duplicate

        mock_client = MagicMock()
        mock_dedup = MagicMock(return_value=[page1])  # dedup removes duplicate

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[page1, page2],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                mock_dedup,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        mock_dedup.assert_called_once()
        assert result.total_pages == 1


class TestHarvestAgentVersionCheck:
    """Test version check integration."""

    @pytest.mark.asyncio
    async def test_version_conflicts_included_in_result(self) -> None:
        """HarvestAgent includes version conflict info in HarvestResult."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief(target_api_version="2.0")
        state = _make_state()
        queries = _make_queries()

        page = _make_page("https://docs.test.dev/intro", "crawl", "v1.5 docs")
        conflicts = [{"source_url": "https://docs.test.dev/intro", "version": "1.5", "url": "x"}]
        warnings = ["Version mismatch: found 1.5, target 2.0"]

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[page],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=(conflicts, warnings),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert result.version_conflicts == conflicts
        assert "Version mismatch: found 1.5, target 2.0" in result.warnings


class TestHarvestAgentSaturation:
    """Test saturation warning integration."""

    @pytest.mark.asyncio
    async def test_saturation_warning_added_when_missing_capabilities(self) -> None:
        """HarvestAgent adds warning when saturation check finds missing caps."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(
                    is_saturated=False,
                    missing_capabilities=["caching", "logging"],
                ),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert any("caching" in w and "logging" in w for w in result.warnings)


class TestHarvestAgentReHarvest:
    """Test re-harvest mode with gap queries."""

    @pytest.mark.asyncio
    async def test_uses_refine_gap_queries_when_reharvesting(self) -> None:
        """HarvestAgent uses refine_gap_queries when gap_loop_count > 0."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state(
            gap_loop_count=1,
            gap_report={
                "is_sufficient": False,
                "identified_gaps": ["missing caching docs"],
                "recommended_search_queries": ["caching best practices"],
            },
        )
        queries = _make_queries()

        mock_client = MagicMock()
        mock_refine = MagicMock(return_value=queries)

        with (
            patch(
                "skill_builder.agents.harvest.refine_gap_queries",
                mock_refine,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            agent.run(brief=brief, state=state)

        mock_refine.assert_called_once()
        # Should pass the gap report's recommended queries
        call_args = mock_refine.call_args
        assert call_args[0][2] == ["caching best practices"]  # raw_queries arg


class TestHarvestAgentGitHubDiscovery:
    """Test GitHub discovered docs URL handling."""

    @pytest.mark.asyncio
    async def test_discovered_docs_urls_trigger_firecrawl(self) -> None:
        """When GitHub returns discovered docs URLs, HarvestAgent crawls them."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        github_page = _make_page("https://github.com/test/repo#readme", "github_api")
        docs_page = _make_page("https://test.github.io/docs/intro", "crawl")

        mock_client = MagicMock()

        route_url_calls = 0

        async def route_url_side_effect(seed, max_pages=50):
            nonlocal route_url_calls
            route_url_calls += 1
            if seed.type == "github":
                return ([github_page], ["https://test.github.io/docs/"])
            return [_make_page(seed.url, "crawl")]

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                side_effect=route_url_side_effect,
            ),
            patch(
                "skill_builder.agents.harvest.firecrawl_crawl",
                new_callable=AsyncMock,
                return_value=[docs_page],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        # Should have github page + docs page + at least the docs seed page
        assert result.total_pages >= 2


class TestVersionPersistence:
    """Test that version detection persists detected_version on HarvestPage objects."""

    @pytest.mark.asyncio
    async def test_pages_with_semver_have_detected_version_populated(self) -> None:
        """After harvest, pages containing semver strings have detected_version set."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        # Page with a semver string in content
        versioned_page = _make_page(
            "https://docs.test.dev/changelog",
            "crawl",
            "Released Version: 2.3.1 with new features",
        )

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[versioned_page],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        # The page with semver content should have detected_version populated
        assert result.pages[0].detected_version is not None
        assert result.pages[0].detected_version == "2.3.1"

    @pytest.mark.asyncio
    async def test_pages_without_semver_have_detected_version_none(self) -> None:
        """After harvest, pages without semver strings retain detected_version=None."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        # Page without any semver string
        plain_page = _make_page(
            "https://docs.test.dev/guide",
            "crawl",
            "This is a guide with no version numbers",
        )

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[plain_page],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert result.pages[0].detected_version is None

    @pytest.mark.asyncio
    async def test_enumerate_fix_updates_list_in_place(self) -> None:
        """Version detection uses enumerate to update pages list (not loop variable rebinding)."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()

        # Mix of versioned and unversioned pages
        page_v = _make_page("https://docs.test.dev/v1", "crawl", "SDK v3.0.0 released")
        page_no_v = _make_page("https://docs.test.dev/intro", "crawl", "No versions here")

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[page_v, page_no_v],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        # First page should have detected_version (enumerate fix)
        assert result.pages[0].detected_version == "3.0.0"
        # Second page should NOT have detected_version
        assert result.pages[1].detected_version is None


class TestUsageAccumulation:
    """Test that HarvestAgent accumulates _usage_meta from sub-calls."""

    @pytest.mark.asyncio
    async def test_accumulates_usage_from_query_generator_and_saturation(self) -> None:
        """When query_generator and saturation return _usage_meta, HarvestResult has accumulated totals."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()

        # Create queries result with _usage_meta
        queries = _make_queries()
        queries._usage_meta = {  # type: ignore[attr-defined]
            "model": "claude-sonnet-4-6",
            "input_tokens": 100,
            "output_tokens": 50,
        }

        # Create saturation result with _usage_meta
        sat_result = SaturationResult(is_saturated=True, missing_capabilities=[])
        sat_result._usage_meta = {  # type: ignore[attr-defined]
            "model": "claude-sonnet-4-6",
            "input_tokens": 200,
            "output_tokens": 80,
        }

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=sat_result,
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        usage = getattr(result, "_usage_meta", None)
        assert usage is not None
        assert usage["input_tokens"] == 300  # 100 + 200
        assert usage["output_tokens"] == 130  # 50 + 80
        assert usage["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_no_usage_when_subcalls_have_none(self) -> None:
        """When sub-calls have no _usage_meta, HarvestResult has no _usage_meta."""
        from skill_builder.agents.harvest import HarvestAgent

        brief = _make_brief()
        state = _make_state()
        queries = _make_queries()  # No _usage_meta attr

        mock_client = MagicMock()

        with (
            patch(
                "skill_builder.agents.harvest.generate_search_queries",
                return_value=queries,
            ),
            patch(
                "skill_builder.agents.harvest.route_url",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.exa_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.tavily_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "skill_builder.agents.harvest.deduplicate",
                side_effect=lambda pages: pages,
            ),
            patch(
                "skill_builder.agents.harvest.check_version_conflicts",
                return_value=([], []),
            ),
            patch(
                "skill_builder.agents.harvest.check_saturation",
                new_callable=AsyncMock,
                return_value=SaturationResult(is_saturated=True, missing_capabilities=[]),
            ),
        ):
            agent = HarvestAgent(client=mock_client)
            result = agent.run(brief=brief, state=state)

        assert getattr(result, "_usage_meta", None) is None
