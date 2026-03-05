"""Tests for the Exa semantic search extraction strategy.

Covers:
- exa_search returns HarvestPages with source_type="exa_search"
- Passes num_results parameter correctly
- Handles empty results gracefully
- Skips results with missing text fields
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skill_builder.models.harvest import HarvestPage


def _make_exa_result(url: str, title: str, text: str | None) -> MagicMock:
    """Create a mock Exa search result."""
    result = MagicMock()
    result.url = url
    result.title = title
    result.text = text
    return result


def _make_search_response(results: list) -> MagicMock:
    """Create a mock Exa SearchResponse."""
    resp = MagicMock()
    resp.results = results
    return resp


class TestExaSearch:
    """Test exa_search function."""

    @pytest.mark.asyncio
    async def test_returns_harvest_pages_with_exa_source_type(self) -> None:
        """exa_search returns HarvestPages with source_type='exa_search'."""
        from skill_builder.harvest.exa_strategy import exa_search

        results = [
            _make_exa_result("https://example.com/1", "Result 1", "Best practices for X"),
            _make_exa_result("https://example.com/2", "Result 2", "Patterns for Y"),
        ]
        mock_response = _make_search_response(results)

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await exa_search("test query", num_results=5)

        assert len(pages) == 2
        for page in pages:
            assert isinstance(page, HarvestPage)
            assert page.source_type == "exa_search"

    @pytest.mark.asyncio
    async def test_passes_num_results_parameter(self) -> None:
        """exa_search passes num_results to Exa.search()."""
        from skill_builder.harvest.exa_strategy import exa_search

        mock_response = _make_search_response([])

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            await exa_search("test query", num_results=7)

        instance.search.assert_called_once()
        call_kwargs = instance.search.call_args
        assert call_kwargs.kwargs.get("num_results") == 7

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self) -> None:
        """exa_search returns empty list when search has no results."""
        from skill_builder.harvest.exa_strategy import exa_search

        mock_response = _make_search_response([])

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await exa_search("test query")

        assert pages == []

    @pytest.mark.asyncio
    async def test_skips_results_with_no_text(self) -> None:
        """exa_search skips results where text is None or empty."""
        from skill_builder.harvest.exa_strategy import exa_search

        results = [
            _make_exa_result("https://example.com/1", "Good", "Has text content"),
            _make_exa_result("https://example.com/2", "No text", None),
            _make_exa_result("https://example.com/3", "Empty text", ""),
        ]
        mock_response = _make_search_response(results)

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await exa_search("test query")

        assert len(pages) == 1
        assert pages[0].title == "Good"

    @pytest.mark.asyncio
    async def test_uses_auto_search_type(self) -> None:
        """exa_search passes type='auto' to Exa.search()."""
        from skill_builder.harvest.exa_strategy import exa_search

        mock_response = _make_search_response([])

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            await exa_search("test query")

        call_kwargs = instance.search.call_args.kwargs
        assert call_kwargs.get("type") == "auto"

    @pytest.mark.asyncio
    async def test_requests_text_contents(self) -> None:
        """exa_search requests text contents with max_characters."""
        from skill_builder.harvest.exa_strategy import exa_search

        mock_response = _make_search_response([])

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            await exa_search("test query")

        call_kwargs = instance.search.call_args.kwargs
        contents = call_kwargs.get("contents")
        assert contents is not None
        assert "text" in contents

    @pytest.mark.asyncio
    async def test_handles_none_title(self) -> None:
        """exa_search handles results with None title."""
        from skill_builder.harvest.exa_strategy import exa_search

        results = [_make_exa_result("https://example.com/1", None, "Some text")]
        mock_response = _make_search_response(results)

        with patch("skill_builder.harvest.exa_strategy.Exa") as MockExa:
            instance = MockExa.return_value
            instance.search = MagicMock(return_value=mock_response)

            pages = await exa_search("test query")

        assert len(pages) == 1
        assert pages[0].title == ""
