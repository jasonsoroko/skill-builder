"""Content router -- maps URL types to extraction strategy functions.

The router dispatches each SeedUrl to the appropriate harvest strategy
based on its `type` field. Strategy functions are async callables that
return a list of HarvestPage objects.

GitHub strategy returns a tuple (pages, discovered_docs_urls); route_url
handles the unwrapping transparently.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from skill_builder.harvest.exa_strategy import exa_search
from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl
from skill_builder.harvest.github_strategy import github_extract
from skill_builder.harvest.tavily_strategy import tavily_search
from skill_builder.models.brief import SeedUrl
from skill_builder.models.harvest import HarvestPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy map: URL type -> strategy function
# ---------------------------------------------------------------------------

# Both "docs" and "blog" use the same firecrawl-based crawl strategy.
# "api_schema" uses a special function that searches for OpenAPI specs first.
# "github" uses github_extract which returns (pages, docs_urls) -- route_url handles this.
STRATEGY_MAP: dict[str, Callable[..., Awaitable[Any]]] = {
    "docs": firecrawl_crawl,
    "github": github_extract,
    "api_schema": None,  # type: ignore[dict-item]  # Set below after api_schema_extract defined
    "blog": firecrawl_crawl,
}


# ---------------------------------------------------------------------------
# API schema extraction with search-first fallback
# ---------------------------------------------------------------------------


async def api_schema_extract(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Extract API schema content, falling back to Firecrawl crawl.

    Per locked decision: search for the OpenAPI/Swagger spec via Exa/Tavily.
    If still not found, fall back to crawling the URL as a docs site with Firecrawl.

    Searches Exa for OpenAPI/Swagger spec URL, then falls back to Firecrawl crawl.
    """
    logger.info("api_schema_extract: searching for OpenAPI spec for %s", url)
    try:
        spec_pages = await exa_search(f"openapi swagger spec {url}", num_results=3)
        if spec_pages:
            logger.info("api_schema_extract: found %d spec results for %s", len(spec_pages), url)
            return spec_pages
    except Exception:
        logger.warning("api_schema_extract: spec search failed for %s, falling back", url)

    logger.info("api_schema_extract: falling back to crawl for %s", url)
    return await firecrawl_crawl(url, max_pages=max_pages)


# Wire up api_schema in STRATEGY_MAP after the function is defined
STRATEGY_MAP["api_schema"] = api_schema_extract


# ---------------------------------------------------------------------------
# Route dispatcher
# ---------------------------------------------------------------------------

# Strategies that return tuples (pages, extra_data) instead of just pages
_TUPLE_STRATEGIES = {github_extract}


async def route_url(
    seed: SeedUrl, max_pages: int = 50
) -> list[HarvestPage] | tuple[list[HarvestPage], list[str]]:
    """Dispatch a seed URL to the correct extraction strategy.

    Falls back to firecrawl_crawl for unknown URL types.

    For github_extract, returns a tuple of (pages, discovered_docs_urls)
    so the caller can schedule additional crawls for discovered docs sites.

    Args:
        seed: A SeedUrl with url and type fields.
        max_pages: Maximum pages to extract.

    Returns:
        List of HarvestPage objects, or tuple of (pages, docs_urls) for GitHub.
    """
    strategy = STRATEGY_MAP.get(seed.type, firecrawl_crawl)
    logger.info("Routing %s (type=%s) to %s", seed.url, seed.type, strategy.__name__)
    result = await strategy(seed.url, max_pages=max_pages)
    return result


# Re-export for convenience
__all__ = [
    "STRATEGY_MAP",
    "api_schema_extract",
    "exa_search",
    "firecrawl_crawl",
    "github_extract",
    "route_url",
    "tavily_search",
]
