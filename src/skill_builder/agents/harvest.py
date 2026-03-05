"""HarvestAgent -- orchestrates parallel content harvesting.

Runs all extraction strategies (Firecrawl, GitHub, Exa, Tavily) in parallel
via asyncio.gather, deduplicates results, checks versions, and runs
saturation pre-filter. Conforms to BaseAgent Protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from anthropic import Anthropic

from skill_builder.harvest.dedup import deduplicate
from skill_builder.harvest.exa_strategy import exa_search
from skill_builder.harvest.firecrawl_strategy import firecrawl_crawl
from skill_builder.harvest.query_generator import generate_search_queries, refine_gap_queries
from skill_builder.harvest.router import route_url
from skill_builder.harvest.saturation import check_saturation
from skill_builder.harvest.tavily_strategy import tavily_search
from skill_builder.harvest.version_check import check_version_conflicts, detect_version
from skill_builder.models.brief import SkillBrief
from skill_builder.models.harvest import HarvestPage, HarvestResult
from skill_builder.models.state import PipelineState
from skill_builder.models.synthesis import GeneratedQueries
from skill_builder.tracing import create_traced_client

logger = logging.getLogger(__name__)

# Rate-limit concurrency per API to avoid throttling (Pitfall 3)
_EXA_SEMAPHORE_LIMIT = 3
_TAVILY_SEMAPHORE_LIMIT = 3


class HarvestAgent:
    """Orchestrates parallel content harvesting.

    Conforms to BaseAgent Protocol: run(**kwargs) -> HarvestResult.

    Steps:
    1. Generate search queries (LLM or template fallback)
    2. Build async task list for all sources
    3. Run all tasks in parallel via asyncio.gather
    4. Handle GitHub discovered docs URLs
    5. Deduplicate combined pages
    6. Detect versions and check conflicts
    7. Run saturation pre-filter
    8. Return HarvestResult
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> HarvestResult:
        """Execute harvest phase.

        Bridges sync BaseAgent Protocol to async internals.

        Expected kwargs:
            brief: SkillBrief
            state: PipelineState
        """
        brief: SkillBrief = kwargs["brief"]
        state: PipelineState = kwargs["state"]

        # If already inside an event loop (e.g., during tests), create a task.
        # Otherwise use asyncio.run() for clean event loop management.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Already in an event loop -- create a future and run in-loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self._harvest(brief, state))
                return future.result()
        else:
            return asyncio.run(self._harvest(brief, state))

    async def _harvest(self, brief: SkillBrief, state: PipelineState) -> HarvestResult:
        """Async harvest orchestration."""
        logger.info("HarvestAgent starting for %s", brief.name)

        # Step 1: Generate search queries and start usage accumulation
        queries = self._generate_queries(brief, state)
        _accumulated_usage = {"model": "claude-sonnet-4-6", "input_tokens": 0, "output_tokens": 0}
        queries_meta = getattr(queries, "_usage_meta", None)
        if queries_meta:
            _accumulated_usage["input_tokens"] += queries_meta["input_tokens"]
            _accumulated_usage["output_tokens"] += queries_meta["output_tokens"]
            _accumulated_usage["model"] = queries_meta["model"]

        logger.info(
            "Generated %d exa + %d tavily queries",
            len(queries.exa_queries),
            len(queries.tavily_queries),
        )

        # Step 2: Build async task list with rate-limiting semaphores
        exa_sem = asyncio.Semaphore(_EXA_SEMAPHORE_LIMIT)
        tavily_sem = asyncio.Semaphore(_TAVILY_SEMAPHORE_LIMIT)

        tasks: list[asyncio.Task[Any]] = []

        # URL extraction tasks
        for seed in brief.seed_urls:
            tasks.append(asyncio.create_task(route_url(seed, brief.max_pages)))

        # Exa search tasks (rate-limited)
        for query in queries.exa_queries:
            tasks.append(asyncio.create_task(self._sem_exa(exa_sem, query)))

        # Tavily search tasks (rate-limited)
        for query in queries.tavily_queries:
            tasks.append(asyncio.create_task(self._sem_tavily(tavily_sem, query)))

        # Step 3: Run all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4: Collect pages and handle GitHub discovered docs URLs
        all_pages: list[HarvestPage] = []
        discovered_docs_urls: list[str] = []
        errors: list[Exception] = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(result)
                logger.warning("Harvest task failed: %s", result)
                continue

            if isinstance(result, tuple) and len(result) == 2:
                # GitHub strategy returns (pages, docs_urls)
                pages, docs_urls = result
                all_pages.extend(pages)
                discovered_docs_urls.extend(docs_urls)
            elif isinstance(result, list):
                all_pages.extend(result)

        # Schedule Firecrawl crawls for discovered docs URLs
        if discovered_docs_urls:
            logger.info(
                "Discovered %d docs URLs from GitHub, scheduling crawls",
                len(discovered_docs_urls),
            )
            crawl_tasks = [
                asyncio.create_task(firecrawl_crawl(url, max_pages=brief.max_pages))
                for url in discovered_docs_urls
            ]
            crawl_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            for crawl_result in crawl_results:
                if isinstance(crawl_result, Exception):
                    logger.warning("Docs URL crawl failed: %s", crawl_result)
                elif isinstance(crawl_result, list):
                    all_pages.extend(crawl_result)

        if errors:
            logger.warning(
                "HarvestAgent: %d tasks failed out of %d total",
                len(errors),
                len(results),
            )

        # Step 5: Deduplicate
        pages = deduplicate(all_pages)
        logger.info("After dedup: %d pages (from %d raw)", len(pages), len(all_pages))

        # Step 6: Version detection and conflict checking
        # FIX: Use enumerate to update the list in-place (model_copy returns
        # a new object; reassigning loop variable does NOT mutate the list)
        for i, page in enumerate(pages):
            versions = detect_version(page.content)
            if versions:
                pages[i] = page.model_copy(update={"detected_version": versions[0]})

        conflicts, version_warnings = check_version_conflicts(pages, brief.target_api_version)

        # Step 7: Saturation pre-filter
        saturation = await check_saturation(self.client, pages, brief.required_capabilities)
        sat_meta = getattr(saturation, "_usage_meta", None)
        if sat_meta:
            _accumulated_usage["input_tokens"] += sat_meta["input_tokens"]
            _accumulated_usage["output_tokens"] += sat_meta["output_tokens"]

        warnings = list(version_warnings)
        if not saturation.is_saturated:
            missing = ", ".join(saturation.missing_capabilities)
            warnings.append(f"Saturation: missing content for {missing}")

        # Step 8: Build and return HarvestResult with accumulated usage
        result = HarvestResult(
            pages=pages,
            total_pages=len(pages),
            warnings=warnings,
            version_conflicts=conflicts,
            queries_used=queries.exa_queries + queries.tavily_queries,
        )

        # Attach accumulated usage metadata if any sub-call provided it
        if _accumulated_usage["input_tokens"] > 0 or _accumulated_usage["output_tokens"] > 0:
            result._usage_meta = _accumulated_usage  # type: ignore[attr-defined]

        logger.info(
            "HarvestAgent complete: %d pages, %d warnings, %d conflicts",
            result.total_pages,
            len(result.warnings),
            len(result.version_conflicts),
        )
        return result

    def _generate_queries(
        self, brief: SkillBrief, state: PipelineState
    ) -> GeneratedQueries:
        """Generate search queries, using gap-based refinement if re-harvesting."""
        if state.gap_loop_count > 0 and state.gap_report:
            raw_queries = state.gap_report.get("recommended_search_queries", [])
            if raw_queries:
                logger.info("Re-harvest mode: refining %d gap queries", len(raw_queries))
                return refine_gap_queries(self.client, brief, raw_queries)

        return generate_search_queries(self.client, brief)

    @staticmethod
    async def _sem_exa(sem: asyncio.Semaphore, query: str) -> list[HarvestPage]:
        """Run exa_search with semaphore rate limiting."""
        async with sem:
            return await exa_search(query)

    @staticmethod
    async def _sem_tavily(sem: asyncio.Semaphore, query: str) -> list[HarvestPage]:
        """Run tavily_search with semaphore rate limiting."""
        async with sem:
            return await tavily_search(query)
