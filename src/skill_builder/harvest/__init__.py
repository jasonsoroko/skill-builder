"""Harvest utility layer for content routing, dedup, version checking, and query generation.

Re-exports primary functions from submodules::

    from skill_builder.harvest import route_url, deduplicate
    from skill_builder.harvest import detect_version, generate_search_queries
"""

from skill_builder.harvest.dedup import content_hash, deduplicate, normalize_url
from skill_builder.harvest.query_generator import (
    generate_search_queries,
    refine_gap_queries,
    template_fallback_queries,
)
from skill_builder.harvest.router import STRATEGY_MAP, route_url
from skill_builder.harvest.version_check import check_version_conflicts, detect_version

__all__ = [
    "STRATEGY_MAP",
    "check_version_conflicts",
    "content_hash",
    "deduplicate",
    "detect_version",
    "generate_search_queries",
    "normalize_url",
    "refine_gap_queries",
    "route_url",
    "template_fallback_queries",
]
