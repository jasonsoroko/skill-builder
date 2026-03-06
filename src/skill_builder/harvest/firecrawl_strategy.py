"""Firecrawl docs site crawling strategy.

Crawls documentation sites with JS rendering via Firecrawl's AsyncFirecrawl
client. Returns markdown content as HarvestPage objects.
"""

from __future__ import annotations

import logging
import os

from firecrawl import AsyncFirecrawl
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from skill_builder.models.harvest import HarvestPage
from skill_builder.resilience import _is_retryable_any, _make_retry_callback

logger = logging.getLogger(__name__)


async def _firecrawl_crawl_with_retry(fc, url: str, max_pages: int):
    """Async Firecrawl crawl with exponential backoff retry."""
    async for attempt in AsyncRetrying(
        wait=wait_exponential_jitter(initial=1.0, max=60.0, jitter=1.0),
        stop=stop_after_attempt(5),
        retry=retry_if_exception(_is_retryable_any),
        reraise=True,
        before_sleep=_make_retry_callback(),
    ):
        with attempt:
            return await fc.crawl(url=url, limit=max_pages, scrape_options={"formats": ["markdown"]})


async def firecrawl_crawl(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Crawl a docs site via Firecrawl and return HarvestPages.

    Uses AsyncFirecrawl with JS rendering. Sets explicit limit matching
    max_pages to avoid timeouts on large sites (Pitfall 2). Has exponential
    backoff retry on transient errors via AsyncRetrying.

    Args:
        url: The documentation site URL to crawl.
        max_pages: Maximum number of pages to crawl.

    Returns:
        List of HarvestPage objects with source_type="crawl".
    """
    fc = AsyncFirecrawl(api_key=os.environ.get("FIRECRAWL_API_KEY", ""))
    logger.info("Starting Firecrawl crawl of %s (limit=%d)", url, max_pages)

    result = await _firecrawl_crawl_with_retry(fc, url, max_pages)

    pages: list[HarvestPage] = []
    for doc in result.data:
        markdown = doc.markdown
        if not markdown:
            continue

        # Extract metadata safely
        meta = doc.metadata_typed if hasattr(doc, "metadata_typed") else doc.metadata
        title = ""
        doc_url = url
        if meta is not None:
            title = getattr(meta, "title", "") or ""
            doc_url = getattr(meta, "source_url", None) or getattr(meta, "url", None) or url

        pages.append(
            HarvestPage(
                url=doc_url,
                title=title,
                content=markdown,
                source_type="crawl",
                source_url=url,
            )
        )

    logger.info("Firecrawl crawl of %s returned %d pages", url, len(pages))
    return pages
