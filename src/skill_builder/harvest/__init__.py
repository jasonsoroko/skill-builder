"""Harvest utility layer for content routing, dedup, version checking, and query generation.

Re-exports primary functions from submodules::

    from skill_builder.harvest import route_url, deduplicate
    from skill_builder.harvest import firecrawl_crawl, github_extract
    from skill_builder.harvest import exa_search, tavily_search
    from skill_builder.harvest import check_saturation
"""

from skill_builder.harvest.dedup import content_hash, deduplicate, normalize_url
from skill_builder.harvest.exa_strategy import exa_search
from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl
from skill_builder.harvest.github_strategy import github_extract
from skill_builder.harvest.query_generator import (
    generate_search_queries,
    refine_gap_queries,
    template_fallback_queries,
)
from skill_builder.harvest.router import STRATEGY_MAP, route_url
from skill_builder.harvest.saturation import check_saturation
from skill_builder.harvest.tavily_strategy import tavily_search
from skill_builder.harvest.version_check import check_version_conflicts, detect_version

__all__ = [
    "STRATEGY_MAP",
    "check_saturation",
    "check_version_conflicts",
    "content_hash",
    "deduplicate",
    "detect_version",
    "exa_search",
    "firecrawl_crawl",
    "generate_search_queries",
    "github_extract",
    "normalize_url",
    "refine_gap_queries",
    "route_url",
    "tavily_search",
    "template_fallback_queries",
]
