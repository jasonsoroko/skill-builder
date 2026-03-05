"""Tavily web search extraction strategy.

Uses Tavily's advanced search to find common errors, version-specific
issues, and current information. Returns results as HarvestPage objects.

Prefers raw_content over content snippet when available (per RESEARCH.md).
"""

from __future__ import annotations

import asyncio
import logging

from tavily import TavilyClient

from skill_builder.models.harvest import HarvestPage

logger = logging.getLogger(__name__)


async def tavily_search(query: str, *, max_results: int = 10) -> list[HarvestPage]:
    """Run a web search via Tavily and return HarvestPages.

    Uses sync TavilyClient wrapped in asyncio.to_thread() for async
    compatibility. Reads TAVILY_API_KEY from environment.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        List of HarvestPage objects with source_type="tavily_search".
    """
    logger.info("Tavily search: %r (max_results=%d)", query, max_results)

    tavily = TavilyClient()  # Reads TAVILY_API_KEY from env

    # Wrap sync call in asyncio.to_thread for async compatibility
    response = await asyncio.to_thread(
        tavily.search,
        query,
        search_depth="advanced",
        max_results=max_results,
        include_raw_content=True,
    )

    pages: list[HarvestPage] = []
    for result in response.get("results", []):
        # Prefer raw_content over content snippet when available
        content = result.get("raw_content") or result.get("content", "")
        if not content:
            continue
        pages.append(
            HarvestPage(
                url=result.get("url", ""),
                title=result.get("title", ""),
                content=content,
                source_type="tavily_search",
            )
        )

    logger.info("Tavily search returned %d pages for %r", len(pages), query)
    return pages
