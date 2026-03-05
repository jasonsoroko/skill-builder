"""Tests for the Tavily web search extraction strategy.

Covers:
- tavily_search returns HarvestPages with source_type="tavily_search"
- Passes max_results and search_depth parameters
- Prefers raw_content over content snippet
- Handles empty results gracefully
- Handles missing raw_content fallback to content
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skill_builder.models.harvest import HarvestPage


class TestTavilySearch:
    """Test tavily_search function."""

    @pytest.mark.asyncio
    async def test_returns_harvest_pages_with_tavily_source_type(self) -> None:
        """tavily_search returns HarvestPages with source_type='tavily_search'."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        mock_response = {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Result 1",
                    "content": "snippet 1",
                    "raw_content": "Full content of result 1",
                },
                {
                    "url": "https://example.com/2",
                    "title": "Result 2",
                    "content": "snippet 2",
                    "raw_content": "Full content of result 2",
                },
            ]
        }

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await tavily_search("test query", max_results=5)

        assert len(pages) == 2
        for page in pages:
            assert isinstance(page, HarvestPage)
            assert page.source_type == "tavily_search"

    @pytest.mark.asyncio
    async def test_passes_search_parameters(self) -> None:
        """tavily_search passes search_depth='advanced' and max_results."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value={"results": []})

            await tavily_search("test query", max_results=15)

        instance.search.assert_called_once()
        call_kwargs = instance.search.call_args.kwargs
        assert call_kwargs.get("search_depth") == "advanced"
        assert call_kwargs.get("max_results") == 15
        assert call_kwargs.get("include_raw_content") is True

    @pytest.mark.asyncio
    async def test_prefers_raw_content_over_snippet(self) -> None:
        """tavily_search uses raw_content when available, not content snippet."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        mock_response = {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Result 1",
                    "content": "short snippet",
                    "raw_content": "Full detailed raw content of the page",
                },
            ]
        }

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await tavily_search("test query")

        assert pages[0].content == "Full detailed raw content of the page"

    @pytest.mark.asyncio
    async def test_falls_back_to_content_when_no_raw_content(self) -> None:
        """tavily_search falls back to content snippet when raw_content is absent."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        mock_response = {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Result 1",
                    "content": "content snippet only",
                },
            ]
        }

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await tavily_search("test query")

        assert pages[0].content == "content snippet only"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self) -> None:
        """tavily_search returns empty list when search has no results."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value={"results": []})

            pages = await tavily_search("test query")

        assert pages == []

    @pytest.mark.asyncio
    async def test_skips_results_with_no_content(self) -> None:
        """tavily_search skips results that have neither raw_content nor content."""
        from skill_builder.harvest.tavily_strategy import tavily_search

        mock_response = {
            "results": [
                {
                    "url": "https://example.com/good",
                    "title": "Good",
                    "content": "has content",
                },
                {
                    "url": "https://example.com/empty",
                    "title": "Empty",
                    "content": "",
                },
            ]
        }

        with patch("skill_builder.harvest.tavily_strategy.TavilyClient") as MockTV:
            instance = MockTV.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await tavily_search("test query")

        assert len(pages) == 1
        assert pages[0].title == "Good"
