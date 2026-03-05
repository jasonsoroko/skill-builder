"""Tests for the Firecrawl extraction strategy.

Covers:
- firecrawl_crawl returns HarvestPages with source_type="crawl"
- Passes limit parameter matching max_pages
- Sets source_url on each page
- Handles empty crawl results gracefully
- Handles crawl errors gracefully
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_builder.models.harvest import HarvestPage


def _make_document(url: str, title: str, markdown: str) -> MagicMock:
    """Create a mock Firecrawl Document."""
    doc = MagicMock()
    doc.markdown = markdown
    meta = MagicMock()
    meta.title = title
    meta.source_url = url
    doc.metadata = meta
    doc.metadata_typed = meta
    return doc


def _make_crawl_job(documents: list) -> MagicMock:
    """Create a mock CrawlJob with .data list."""
    job = MagicMock()
    job.data = documents
    job.status = "completed"
    return job


class TestFirecrawlCrawl:
    """Test firecrawl_crawl function."""

    @pytest.mark.asyncio
    async def test_returns_harvest_pages_with_crawl_source_type(self) -> None:
        """firecrawl_crawl returns HarvestPages with source_type='crawl'."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        docs = [
            _make_document("https://docs.example.com/page1", "Page 1", "# Page 1 content"),
            _make_document("https://docs.example.com/page2", "Page 2", "# Page 2 content"),
        ]
        mock_job = _make_crawl_job(docs)

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            pages = await firecrawl_crawl("https://docs.example.com", max_pages=10)

        assert len(pages) == 2
        for page in pages:
            assert isinstance(page, HarvestPage)
            assert page.source_type == "crawl"

    @pytest.mark.asyncio
    async def test_passes_limit_matching_max_pages(self) -> None:
        """firecrawl_crawl passes limit=max_pages to crawl()."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        mock_job = _make_crawl_job([])

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            await firecrawl_crawl("https://docs.example.com", max_pages=25)

        instance.crawl.assert_called_once()
        call_kwargs = instance.crawl.call_args
        assert call_kwargs.kwargs.get("limit") == 25 or call_kwargs[1].get("limit") == 25

    @pytest.mark.asyncio
    async def test_sets_source_url_on_each_page(self) -> None:
        """firecrawl_crawl sets source_url to the original seed URL."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        docs = [_make_document("https://docs.example.com/sub", "Sub", "content")]
        mock_job = _make_crawl_job(docs)

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            pages = await firecrawl_crawl("https://docs.example.com", max_pages=10)

        assert pages[0].source_url == "https://docs.example.com"

    @pytest.mark.asyncio
    async def test_empty_crawl_result_returns_empty_list(self) -> None:
        """firecrawl_crawl returns empty list when crawl produces no data."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        mock_job = _make_crawl_job([])

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            pages = await firecrawl_crawl("https://docs.example.com")

        assert pages == []

    @pytest.mark.asyncio
    async def test_skips_documents_with_no_markdown(self) -> None:
        """firecrawl_crawl skips documents where markdown is None or empty."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        good_doc = _make_document("https://docs.example.com/good", "Good", "# Content")
        empty_doc = _make_document("https://docs.example.com/empty", "Empty", "")
        empty_doc.markdown = None

        mock_job = _make_crawl_job([good_doc, empty_doc])

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            pages = await firecrawl_crawl("https://docs.example.com")

        assert len(pages) == 1
        assert pages[0].title == "Good"

    @pytest.mark.asyncio
    async def test_requests_markdown_format(self) -> None:
        """firecrawl_crawl passes scrape_options with markdown format."""
        from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl

        mock_job = _make_crawl_job([])

        with patch(
            "skill_builder.harvest.firecrawl_strategy.AsyncFirecrawl"
        ) as MockFC:
            instance = MockFC.return_value
            instance.crawl = AsyncMock(return_value=mock_job)

            await firecrawl_crawl("https://docs.example.com")

        call_kwargs = instance.crawl.call_args[1]
        scrape_opts = call_kwargs.get("scrape_options")
        assert scrape_opts is not None
        # Should request markdown format
        formats = scrape_opts.get("formats", [])
        assert "markdown" in formats
