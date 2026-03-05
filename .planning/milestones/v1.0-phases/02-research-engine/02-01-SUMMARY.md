---
phase: 02-research-engine
plan: 01
subsystem: harvest
tags: [pydantic, dedup, sha256, semver, anthropic, firecrawl, exa, tavily]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Pydantic models (HarvestPage, HarvestResult, ResearchCategory, CategorizedResearch), BaseAgent Protocol, resilience.py, tracing.py
provides:
  - Extended HarvestPage/HarvestResult with source attribution and version tracking
  - ContentItem model for source-attributed content in ResearchCategory
  - GeneratedQueries and SaturationResult models
  - Harvest router mapping URL types to extraction strategies
  - Content deduplication by normalized URL and SHA-256 content hash
  - Version detection (semver regex) and cross-source conflict flagging
  - LLM query generator with template fallback for Exa/Tavily
affects: [02-02-PLAN, 02-03-PLAN, harvest-agent, organizer-agent, gap-analyzer-agent]

# Tech tracking
tech-stack:
  added: [firecrawl-py 4.18.0, exa-py 2.7.0, tavily-python 0.7.22, pytest-asyncio 1.3.0]
  patterns: [strategy-map dispatch, URL normalization, whitespace-normalized content hashing, LLM structured output with fallback]

key-files:
  created:
    - src/skill_builder/harvest/__init__.py
    - src/skill_builder/harvest/router.py
    - src/skill_builder/harvest/dedup.py
    - src/skill_builder/harvest/version_check.py
    - src/skill_builder/harvest/query_generator.py
    - tests/test_harvest_router.py
    - tests/test_dedup.py
    - tests/test_version_check.py
    - tests/test_query_generator.py
  modified:
    - pyproject.toml
    - src/skill_builder/models/harvest.py
    - src/skill_builder/models/synthesis.py
    - src/skill_builder/models/__init__.py
    - src/skill_builder/agents/stubs.py
    - tests/test_models.py

key-decisions:
  - "Used model_copy() in deduplicate() to set content_hash without mutating original HarvestPage objects"
  - "Router uses mutable STRATEGY_MAP dict so Plan 02 can replace placeholders with real strategy functions"
  - "api_schema_extract defined as named function (not lambda) in router for testability and future search logic"

patterns-established:
  - "Strategy dispatch: STRATEGY_MAP[seed.type] -> async callable returning list[HarvestPage]"
  - "URL normalization: lowercase scheme/netloc, strip trailing slash, sort query params, strip fragment"
  - "Content dedup: whitespace-normalized SHA-256 hash for near-identical content"
  - "LLM with fallback: try messages.parse() with Pydantic model, catch all exceptions, fall back to templates"

requirements-completed: [HARV-01, HARV-04, HARV-07, HARV-08]

# Metrics
duration: 7min
completed: 2026-03-05
---

# Phase 2 Plan 1: Harvest Utilities Summary

**Extended Pydantic models for source attribution/version tracking, 4 harvest utility modules (router, dedup, version check, query generator) with full test coverage**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-05T16:54:05Z
- **Completed:** 2026-03-05T17:00:40Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- Installed 3 Phase 2 dependencies (firecrawl-py, exa-py, tavily-python) and pytest-asyncio for async tests
- Extended HarvestPage/HarvestResult with source_url, detected_version, warnings, version_conflicts, queries_used fields
- Added ContentItem, GeneratedQueries, SaturationResult models; changed ResearchCategory.content to list[ContentItem]
- Built 4 harvest utility modules: content router with strategy map, URL+content dedup, semver version detection with conflict flagging, LLM query generator with template fallback

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and extend Pydantic models** - `9b1ea63` (feat)
2. **Task 2: Harvest utility modules** - `b972ec8` (feat)

_Both tasks followed TDD: RED (failing tests) -> GREEN (implementation) -> verify_

## Files Created/Modified
- `src/skill_builder/harvest/__init__.py` - Package re-exports for all harvest utilities
- `src/skill_builder/harvest/router.py` - STRATEGY_MAP + route_url dispatcher + api_schema_extract
- `src/skill_builder/harvest/dedup.py` - normalize_url, content_hash, deduplicate
- `src/skill_builder/harvest/version_check.py` - detect_version, check_version_conflicts
- `src/skill_builder/harvest/query_generator.py` - generate_search_queries, template_fallback_queries, refine_gap_queries
- `src/skill_builder/models/harvest.py` - HarvestPage/HarvestResult extended fields
- `src/skill_builder/models/synthesis.py` - ContentItem, GeneratedQueries, SaturationResult, updated ResearchCategory
- `src/skill_builder/models/__init__.py` - Re-exports for new models
- `src/skill_builder/agents/stubs.py` - StubOrganizerAgent updated to use ContentItem
- `tests/test_models.py` - 15 new model extension tests
- `tests/test_harvest_router.py` - 6 router tests (async, strategy dispatch, fallback)
- `tests/test_dedup.py` - 17 dedup tests (URL normalization, content hash, deduplication)
- `tests/test_version_check.py` - 12 version detection and conflict tests
- `tests/test_query_generator.py` - 9 query generator tests (template, LLM mock, fallback)

## Decisions Made
- Used `model_copy()` in `deduplicate()` to avoid mutating input HarvestPage objects (immutability pattern)
- Router's STRATEGY_MAP is a mutable dict at module level so Plan 02 can swap placeholder strategies for real implementations without modifying router.py
- `api_schema_extract` is a named function rather than a lambda in STRATEGY_MAP for testability and to support future search-first logic
- Added `pytest-asyncio` as dev dependency for async router tests rather than wrapping in `asyncio.run()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pytest-asyncio for async test support**
- **Found during:** Task 2 (writing router tests)
- **Issue:** pytest.mark.asyncio requires pytest-asyncio package, not installed
- **Fix:** `uv add --dev "pytest-asyncio>=0.25"` -- added as dev dependency
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** All async router tests pass
- **Committed in:** b972ec8 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for async test execution. No scope creep.

## Issues Encountered
None

## User Setup Required

External services will require API keys for Plan 02 (not this plan):
- `FIRECRAWL_API_KEY` from https://firecrawl.dev/app/api-keys
- `EXA_API_KEY` from https://dashboard.exa.ai/api-keys
- `TAVILY_API_KEY` from https://app.tavily.com/home
- `GITHUB_TOKEN` (optional) from https://github.com/settings/tokens

These are documented in the plan frontmatter but not needed until Plan 02 implements real extraction strategies.

## Next Phase Readiness
- All harvest utility modules ready for Plan 02 to build real extraction strategies on top of
- Router STRATEGY_MAP has placeholders that Plan 02 replaces with firecrawl_strategy, github_strategy, exa_strategy, tavily_strategy
- Model contracts (HarvestPage, ContentItem, GeneratedQueries) are stable for Plan 02 and Plan 03 agents
- 149 tests passing (59 new in this plan)

---
*Phase: 02-research-engine*
*Completed: 2026-03-05*
