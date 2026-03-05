"""Exa semantic search extraction strategy.

Uses Exa's neural search to find best practices, patterns, and usage
examples. Returns results as HarvestPage objects.

Per RESEARCH.md open question: uses sync Exa wrapped in asyncio.to_thread()
as the primary approach since AsyncExa availability is not guaranteed.
"""

from __future__ import annotations

import asyncio
import logging

from exa_py import Exa

from skill_builder.models.harvest import HarvestPage
from skill_builder.resilience import api_retry_any

logger = logging.getLogger(__name__)


@api_retry_any()
def _exa_search_sync(exa, query: str, num_results: int):
    """Sync Exa search call with retry wrapper."""
    return exa.search(
        query,
        num_results=num_results,
        type="auto",
        contents={"text": {"max_characters": 10000}},
    )


async def exa_search(query: str, *, num_results: int = 10) -> list[HarvestPage]:
    """Run a semantic search via Exa and return HarvestPages.

    Uses sync Exa client wrapped in asyncio.to_thread() for async
    compatibility. Reads EXA_API_KEY from environment. The inner sync
    call has exponential backoff retry via api_retry_any.

    Args:
        query: Semantic search query string.
        num_results: Maximum number of results to return.

    Returns:
        List of HarvestPage objects with source_type="exa_search".
    """
    logger.info("Exa search: %r (num_results=%d)", query, num_results)

    exa = Exa()  # Reads EXA_API_KEY from env

    # Wrap sync call (with retry) in asyncio.to_thread for async compatibility
    response = await asyncio.to_thread(_exa_search_sync, exa, query, num_results)

    pages: list[HarvestPage] = []
    for result in response.results:
        text = result.text
        if not text:
            continue
        pages.append(
            HarvestPage(
                url=result.url,
                title=result.title or "",
                content=text,
                source_type="exa_search",
            )
        )

    logger.info("Exa search returned %d pages for %r", len(pages), query)
    return pages
