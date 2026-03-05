"""Content router -- maps URL types to extraction strategy functions.

The router dispatches each SeedUrl to the appropriate harvest strategy
based on its `type` field. Strategy functions are async callables that
return a list of HarvestPage objects.

Strategies are placeholder async functions at this stage. Real implementations
(firecrawl_strategy, github_strategy, etc.) replace them in Plan 02.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from skill_builder.models.brief import SeedUrl
from skill_builder.models.harvest import HarvestPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Placeholder strategy functions (replaced by real strategies in Plan 02)
# ---------------------------------------------------------------------------


async def _firecrawl_crawl_placeholder(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Placeholder for Firecrawl docs/blog crawling strategy."""
    raise NotImplementedError(
        "firecrawl_crawl strategy not yet implemented -- see Plan 02"
    )


async def _github_extract_placeholder(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Placeholder for GitHub repo extraction strategy."""
    raise NotImplementedError(
        "github_extract strategy not yet implemented -- see Plan 02"
    )


# ---------------------------------------------------------------------------
# Strategy map: URL type -> strategy function
# ---------------------------------------------------------------------------

# Both "docs" and "blog" use the same firecrawl-based crawl strategy.
# "api_schema" uses a special function that searches for OpenAPI specs first.
STRATEGY_MAP: dict[str, Callable[..., Awaitable[list[HarvestPage]]]] = {
    "docs": _firecrawl_crawl_placeholder,
    "github": _github_extract_placeholder,
    "api_schema": None,  # type: ignore[dict-item]  # Set below after api_schema_extract defined
    "blog": _firecrawl_crawl_placeholder,
}


# ---------------------------------------------------------------------------
# API schema extraction with search-first fallback
# ---------------------------------------------------------------------------


async def api_schema_extract(url: str, *, max_pages: int = 50) -> list[HarvestPage]:
    """Extract API schema content, falling back to Firecrawl crawl.

    Per locked decision: search for the OpenAPI/Swagger spec via Exa/Tavily.
    If still not found, fall back to crawling the URL as a docs site with Firecrawl.

    At this stage, the Exa/Tavily search is a placeholder -- it always falls
    back to Firecrawl crawl. Real search integration comes in Plan 02.
    """
    # TODO(Plan 02): Search for OpenAPI spec via Exa/Tavily before falling back
    logger.info("api_schema_extract: no spec search yet, falling back to crawl for %s", url)
    return await _firecrawl_crawl_placeholder(url, max_pages=max_pages)


# Wire up api_schema in STRATEGY_MAP after the function is defined
STRATEGY_MAP["api_schema"] = api_schema_extract


# ---------------------------------------------------------------------------
# Route dispatcher
# ---------------------------------------------------------------------------


async def route_url(seed: SeedUrl, max_pages: int = 50) -> list[HarvestPage]:
    """Dispatch a seed URL to the correct extraction strategy.

    Falls back to firecrawl_crawl for unknown URL types.

    Args:
        seed: A SeedUrl with url and type fields.
        max_pages: Maximum pages to extract.

    Returns:
        List of HarvestPage objects from the chosen strategy.
    """
    strategy = STRATEGY_MAP.get(seed.type, _firecrawl_crawl_placeholder)
    logger.info("Routing %s (type=%s) to %s", seed.url, seed.type, strategy.__name__)
    return await strategy(seed.url, max_pages=max_pages)
