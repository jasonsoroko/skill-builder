"""Tests for the harvest content router.

Covers:
- STRATEGY_MAP has correct keys (docs, github, api_schema, blog)
- route_url dispatches to correct strategy via mocks
- Unknown type falls back to firecrawl
- api_schema_extract fallback logic (search empty -> falls back to crawl)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from skill_builder.models.brief import SeedUrl
from skill_builder.models.harvest import HarvestPage


class TestStrategyMap:
    """Test that STRATEGY_MAP has the correct URL type keys."""

    def test_strategy_map_has_all_url_types(self) -> None:
        """STRATEGY_MAP contains entries for docs, github, api_schema, blog."""
        from skill_builder.harvest.router import STRATEGY_MAP

        assert "docs" in STRATEGY_MAP
        assert "github" in STRATEGY_MAP
        assert "api_schema" in STRATEGY_MAP
        assert "blog" in STRATEGY_MAP

    def test_strategy_map_docs_and_blog_share_strategy(self) -> None:
        """docs and blog both map to firecrawl_crawl."""
        from skill_builder.harvest.router import STRATEGY_MAP

        assert STRATEGY_MAP["docs"] is STRATEGY_MAP["blog"]


class TestRouteUrl:
    """Test route_url dispatches correctly."""

    @pytest.mark.asyncio
    async def test_route_url_dispatches_docs_type(self) -> None:
        """route_url dispatches docs type to the docs strategy."""
        from skill_builder.harvest import router

        mock_page = HarvestPage(
            url="https://docs.example.com/page",
            title="Test",
            content="Test content",
            source_type="crawl",
        )
        mock_strategy = AsyncMock(return_value=[mock_page])

        with patch.dict(router.STRATEGY_MAP, {"docs": mock_strategy}):
            seed = SeedUrl(url="https://docs.example.com", type="docs")
            result = await router.route_url(seed, max_pages=10)

        mock_strategy.assert_called_once_with("https://docs.example.com", max_pages=10)
        assert len(result) == 1
        assert result[0].url == "https://docs.example.com/page"

    @pytest.mark.asyncio
    async def test_route_url_unknown_type_falls_back_to_firecrawl(self) -> None:
        """route_url with unknown type falls back to firecrawl_crawl."""
        from skill_builder.harvest import router

        mock_page = HarvestPage(
            url="https://example.com/page",
            title="Fallback",
            content="Fallback content",
            source_type="crawl",
        )
        mock_crawl = AsyncMock(return_value=[mock_page])

        with patch.object(router, "_firecrawl_crawl_placeholder", mock_crawl):
            # Create a seed with a known type but override the map to test fallback
            seed = SeedUrl(url="https://example.com", type="docs")
            # Remove docs from map to trigger fallback
            original_map = router.STRATEGY_MAP.copy()
            router.STRATEGY_MAP.clear()
            try:
                result = await router.route_url(seed, max_pages=5)
            finally:
                router.STRATEGY_MAP.update(original_map)

        assert len(result) == 1
        mock_crawl.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_url_github_type_dispatches(self) -> None:
        """route_url dispatches github type correctly."""
        from skill_builder.harvest import router

        mock_page = HarvestPage(
            url="https://github.com/owner/repo",
            title="README",
            content="# Repo README",
            source_type="github_api",
        )
        mock_strategy = AsyncMock(return_value=[mock_page])

        with patch.dict(router.STRATEGY_MAP, {"github": mock_strategy}):
            seed = SeedUrl(url="https://github.com/owner/repo", type="github")
            result = await router.route_url(seed, max_pages=20)

        mock_strategy.assert_called_once_with("https://github.com/owner/repo", max_pages=20)
        assert result[0].source_type == "github_api"


class TestApiSchemaExtract:
    """Test api_schema_extract fallback logic."""

    @pytest.mark.asyncio
    async def test_api_schema_extract_falls_back_to_crawl(self) -> None:
        """api_schema_extract falls back to firecrawl_crawl when search finds nothing."""
        from skill_builder.harvest.router import api_schema_extract

        mock_page = HarvestPage(
            url="https://api.example.com/docs",
            title="API Docs",
            content="API documentation",
            source_type="crawl",
        )

        with patch(
            "skill_builder.harvest.router._firecrawl_crawl_placeholder",
            new_callable=AsyncMock,
            return_value=[mock_page],
        ):
            result = await api_schema_extract("https://api.example.com", max_pages=10)

        assert len(result) == 1
        assert result[0].url == "https://api.example.com/docs"
