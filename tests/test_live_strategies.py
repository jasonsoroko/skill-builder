"""Layer 1: Strategy isolation tests -- verify each harvest strategy against real APIs.

Each test calls one extraction strategy with minimal parameters and verifies
the returned HarvestPage objects. Total cost: ~$0.05.
Run with: pytest -m live --tb=short -v
"""

from __future__ import annotations

import os

import pytest

from skill_builder.models.harvest import HarvestPage

pytestmark = [pytest.mark.live, pytest.mark.timeout(120)]


def _skip_if_no_key(env_var: str) -> None:
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


def _assert_valid_pages(pages: list[HarvestPage], expected_source_type: str) -> None:
    """Shared assertions for a list of HarvestPage results."""
    assert isinstance(pages, list)
    assert len(pages) > 0, f"Expected at least 1 page, got 0"
    for page in pages:
        assert isinstance(page, HarvestPage)
        assert page.content, f"Page {page.url} has empty content"
        assert page.url, f"Page has empty url"
        assert page.source_type == expected_source_type


class TestLiveStrategies:
    """Verify each harvest strategy returns valid HarvestPage objects from real endpoints."""

    @pytest.mark.asyncio
    async def test_firecrawl_crawl_real(self) -> None:
        """Firecrawl crawl returns HarvestPages from a real docs site."""
        _skip_if_no_key("FIRECRAWL_API_KEY")
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        pages = await firecrawl_crawl("https://docs.exa.ai/", max_pages=3)
        _assert_valid_pages(pages, "crawl")

    @pytest.mark.asyncio
    async def test_exa_search_real(self) -> None:
        """Exa search returns HarvestPages from a semantic search."""
        _skip_if_no_key("EXA_API_KEY")
        from skill_builder.harvest.exa_strategy import exa_search

        pages = await exa_search(
            "Exa API python SDK semantic search", num_results=3
        )
        _assert_valid_pages(pages, "exa_search")

    @pytest.mark.asyncio
    async def test_tavily_search_real(self) -> None:
        """Tavily search returns HarvestPages from a web search."""
        _skip_if_no_key("TAVILY_API_KEY")
        from skill_builder.harvest.tavily_strategy import tavily_search

        pages = await tavily_search(
            "Tavily python SDK advanced web search", max_results=3
        )
        _assert_valid_pages(pages, "tavily_search")

    @pytest.mark.asyncio
    async def test_github_extract_real(self) -> None:
        """GitHub extract returns HarvestPages from a real repo."""
        from skill_builder.harvest.github_strategy import github_extract

        pages, docs_urls = await github_extract(
            "https://github.com/mendableai/firecrawl", max_pages=5
        )
        assert isinstance(pages, list)
        assert len(pages) >= 1, "Expected at least README page"
        for page in pages:
            assert isinstance(page, HarvestPage)
            assert page.content
            assert page.source_type == "github_api"

        assert isinstance(docs_urls, list)
