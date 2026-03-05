"""Firecrawl docs site crawling strategy.

Crawls documentation sites with JS rendering via Firecrawl's AsyncFirecrawl
client. Returns markdown content as HarvestPage objects.
"""

from __future__ import annotations

import logging
import os

from firecrawl import AsyncFirecrawl

from skill_builder.models.harvest import HarvestPage

logger = logging.getLogger(__name__)


async def firecrawl_crawl(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Crawl a docs site via Firecrawl and return HarvestPages.

    Uses AsyncFirecrawl with JS rendering. Sets explicit limit matching
    max_pages to avoid timeouts on large sites (Pitfall 2).

    Args:
        url: The documentation site URL to crawl.
        max_pages: Maximum number of pages to crawl.

    Returns:
        List of HarvestPage objects with source_type="crawl".
    """
    fc = AsyncFirecrawl(api_key=os.environ.get("FIRECRAWL_API_KEY", ""))
    logger.info("Starting Firecrawl crawl of %s (limit=%d)", url, max_pages)

    result = await fc.crawl(
        url,
        limit=max_pages,
        scrape_options={"formats": ["markdown"]},
    )

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
