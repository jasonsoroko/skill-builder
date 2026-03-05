---
phase: 02-research-engine
plan: 02
subsystem: harvest
tags: [firecrawl, github-api, exa, tavily, asyncio, parallel-harvest, saturation]

# Dependency graph
requires:
  - phase: 02-research-engine/01
    provides: harvest utility layer (router, dedup, version_check, query_generator)
  - phase: 01-foundation
    provides: BaseAgent Protocol, resilience.py, tracing.py, all data models
provides:
  - Firecrawl docs site crawling strategy (firecrawl_crawl)
  - GitHub REST API extraction strategy (github_extract)
  - Exa semantic search strategy (exa_search)
  - Tavily web search strategy (tavily_search)
  - Saturation pre-filter (check_saturation)
  - HarvestAgent with parallel orchestration via asyncio.gather
affects: [02-research-engine/03, 03-output-pipeline]

# Tech tracking
tech-stack:
  added: [firecrawl AsyncFirecrawl, exa_py Exa, tavily TavilyClient, httpx AsyncClient]
  patterns: [asyncio.gather parallel harvest, semaphore rate limiting, sync-to-async ThreadPoolExecutor bridge, fail-open saturation check]

key-files:
  created:
    - src/skill_builder/harvest/firecrawl_strategy.py
    - src/skill_builder/harvest/github_strategy.py
    - src/skill_builder/harvest/exa_strategy.py
    - src/skill_builder/harvest/tavily_strategy.py
    - src/skill_builder/harvest/saturation.py
    - src/skill_builder/agents/harvest.py
    - tests/test_firecrawl_strategy.py
    - tests/test_exa_strategy.py
    - tests/test_tavily_strategy.py
    - tests/test_saturation.py
    - tests/test_harvest_agent.py
  modified:
    - src/skill_builder/harvest/router.py
    - src/skill_builder/harvest/__init__.py
    - tests/test_harvest_router.py

key-decisions:
  - "Used sync Exa/Tavily clients wrapped in asyncio.to_thread() rather than untested async variants"
  - "GitHub strategy returns tuple (pages, discovered_docs_urls) for caller to schedule additional crawls"
  - "ThreadPoolExecutor bridge in HarvestAgent.run() for sync-to-async Protocol conformance"
  - "Saturation check fails open (returns saturated=True on error) since Gap Analyzer is real quality gate"

patterns-established:
  - "Strategy pattern: each extraction source is a standalone async function with consistent signature"
  - "Semaphore rate limiting: max 3 concurrent Exa + max 3 concurrent Tavily to avoid throttling"
  - "Fail-open safety: saturation pre-filter never blocks the pipeline on errors"
  - "Tuple return for multi-output strategies: GitHub returns (pages, docs_urls)"

requirements-completed: [HARV-02, HARV-03, HARV-05, HARV-06, HARV-09, HARV-10]

# Metrics
duration: 8min
completed: 2026-03-05
---

# Phase 02 Plan 02: Extraction Strategies + HarvestAgent Summary

**Four extraction strategies (Firecrawl, GitHub API, Exa, Tavily) with parallel HarvestAgent orchestration via asyncio.gather, saturation pre-filter, and semaphore rate limiting**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-05T17:03:31Z
- **Completed:** 2026-03-05T17:11:31Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Implemented all 4 extraction strategies: Firecrawl (docs crawling), GitHub (REST API), Exa (semantic search), Tavily (web search)
- Built HarvestAgent orchestrating parallel harvest via asyncio.gather with semaphore-based rate limiting
- Saturation pre-filter with cheap Sonnet call that fails open on errors
- GitHub strategy auto-discovers published docs site URLs and returns them for additional crawling
- 184 tests passing (added 35 new tests), all with fully mocked external APIs

## Task Commits

Each task was committed atomically:

1. **Task 1: Extraction strategies** (TDD)
   - `94088ff` test(02-02): add failing tests for extraction strategies
   - `a572d8e` feat(02-02): implement extraction strategies and wire router

2. **Task 2: Saturation + HarvestAgent** (TDD)
   - `093d22f` test(02-02): add failing tests for saturation and HarvestAgent
   - `20ab6fa` feat(02-02): implement saturation pre-filter and HarvestAgent orchestrator

_Note: TDD tasks have test-first then implementation commits._

## Files Created/Modified
- `src/skill_builder/harvest/firecrawl_strategy.py` - AsyncFirecrawl crawl with limit, markdown format
- `src/skill_builder/harvest/github_strategy.py` - GitHub REST API extraction (README, docs/, examples/, link following, docs discovery)
- `src/skill_builder/harvest/exa_strategy.py` - Exa semantic search with asyncio.to_thread() wrapper
- `src/skill_builder/harvest/tavily_strategy.py` - Tavily web search preferring raw_content
- `src/skill_builder/harvest/saturation.py` - Lightweight LLM saturation pre-filter
- `src/skill_builder/agents/harvest.py` - HarvestAgent with parallel orchestration
- `src/skill_builder/harvest/router.py` - Replaced placeholders with real strategy imports
- `src/skill_builder/harvest/__init__.py` - Added all new re-exports
- `tests/test_firecrawl_strategy.py` - 6 tests for Firecrawl strategy
- `tests/test_exa_strategy.py` - 7 tests for Exa strategy
- `tests/test_tavily_strategy.py` - 6 tests for Tavily strategy
- `tests/test_saturation.py` - 7 tests for saturation pre-filter
- `tests/test_harvest_agent.py` - 9 tests for HarvestAgent
- `tests/test_harvest_router.py` - Updated to match new router structure

## Decisions Made
- Used sync Exa/Tavily wrapped in asyncio.to_thread() over untested AsyncExa/AsyncTavilyClient -- pragmatic approach given unclear async client availability
- GitHub strategy returns tuple (pages, discovered_docs_urls) so HarvestAgent can schedule Firecrawl crawls for auto-discovered docs sites
- HarvestAgent uses ThreadPoolExecutor bridge to call asyncio.run() from sync Protocol.run() when already inside an event loop (test compatibility)
- Saturation fails open (returns saturated=True on error) -- the Gap Analyzer downstream is the real quality gate
- api_schema_extract now searches Exa for OpenAPI specs before falling back to Firecrawl crawl

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing router test referencing removed placeholder**
- **Found during:** Task 1 (Router wiring)
- **Issue:** test_harvest_router.py referenced `_firecrawl_crawl_placeholder` which was removed when real strategies were wired in
- **Fix:** Updated test to patch `firecrawl_crawl` instead; updated api_schema test to mock new exa_search+firecrawl_crawl flow
- **Files modified:** tests/test_harvest_router.py
- **Verification:** All 6 router tests pass
- **Committed in:** a572d8e (Task 1 implementation commit)

**2. [Rule 3 - Blocking] asyncio.run() fails inside pytest-asyncio event loop**
- **Found during:** Task 2 (HarvestAgent tests)
- **Issue:** HarvestAgent.run() called asyncio.run() which fails when already inside an event loop (pytest-asyncio)
- **Fix:** Added ThreadPoolExecutor bridge that detects running event loop and offloads to thread
- **Files modified:** src/skill_builder/agents/harvest.py
- **Verification:** All 9 HarvestAgent tests pass
- **Committed in:** 20ab6fa (Task 2 implementation commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations.

## User Setup Required
None - no external service configuration required. API keys (FIRECRAWL_API_KEY, EXA_API_KEY, TAVILY_API_KEY, GITHUB_TOKEN) are read from environment at runtime.

## Next Phase Readiness
- All extraction strategies implemented and tested
- HarvestAgent fully orchestrates the harvest phase
- Ready for Plan 03: synthesis agents (Organizer, Gap Analyzer, Learner)
- The StubHarvestAgent can be swapped for the real HarvestAgent in the conductor

## Self-Check: PASSED

All 11 created files exist. All 4 task commits verified.

---
*Phase: 02-research-engine*
*Completed: 2026-03-05*
