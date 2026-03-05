---
phase: 04-integration-wiring
plan: 01
subsystem: resilience
tags: [tenacity, retry, exponential-backoff, firecrawl, exa, tavily, httpx, version-detection]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: api_retry decorator, _is_retryable classifier, test-friendly retry timings
  - phase: 02-research-engine
    provides: strategy functions (firecrawl, exa, tavily, github), HarvestAgent, detect_version
provides:
  - _is_retryable_any unified classifier covering all SDK transient errors
  - api_retry_any decorator for non-Anthropic API calls
  - _make_retry_callback for CLI-visible retry messages
  - Retry wrappers on all 4 strategy functions
  - Fixed version detection persistence (enumerate fix)
  - HarvestAgent usage accumulation from sub-calls
affects: [04-02, conductor-budget-wiring, tracing-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sync SDK calls wrapped with @api_retry_any then passed to asyncio.to_thread"
    - "Async SDK calls wrapped with tenacity AsyncRetrying"
    - "httpx calls wrapped with _httpx_get_with_retry helper"
    - "Usage accumulation via getattr(result, '_usage_meta', None) pattern"
    - "enumerate + pages[i] assignment for in-place list update with model_copy"

key-files:
  created: []
  modified:
    - src/skill_builder/resilience.py
    - src/skill_builder/harvest/firecrawl_strategy.py
    - src/skill_builder/harvest/exa_strategy.py
    - src/skill_builder/harvest/tavily_strategy.py
    - src/skill_builder/harvest/github_strategy.py
    - src/skill_builder/agents/harvest.py
    - tests/test_resilience.py
    - tests/test_harvest_agent.py

key-decisions:
  - "Unified _is_retryable_any covers all SDKs in one classifier rather than per-SDK wrappers"
  - "Exa retry on requests.ConnectionError/Timeout only -- not generic ValueError (avoids retrying auth errors)"
  - "Retry callback uses print() for CLI visibility per locked decision"
  - "Usage accumulation as getattr pattern -- no structural changes to result models"

patterns-established:
  - "Sync retry helper pattern: @api_retry_any decorated sync function passed to asyncio.to_thread"
  - "Async retry helper pattern: AsyncRetrying context manager wrapping native async calls"
  - "httpx retry helper: _httpx_get_with_retry wrapping individual GET calls"

requirements-completed: [RES-01, HARV-08]

# Metrics
duration: 6min
completed: 2026-03-05
---

# Phase 4 Plan 01: Retry Wiring and Version Fix Summary

**Unified exponential backoff retry across all SDK calls (Firecrawl, Exa, Tavily, GitHub httpx) with CLI-visible retry messages, fixed version detection loop variable rebinding bug, and HarvestAgent usage accumulation from sub-calls**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-05T22:24:48Z
- **Completed:** 2026-03-05T22:30:40Z
- **Tasks:** 2 (both TDD: RED-GREEN)
- **Files modified:** 8

## Accomplishments
- All external API calls (Firecrawl, Exa, Tavily, GitHub) now have exponential backoff retry on transient failures (RES-01)
- Version detection persists detected_version on HarvestPage objects via enumerate fix (HARV-08)
- HarvestAgent accumulates _usage_meta from query_generator and saturation sub-calls (ready for CORE-08 budget wiring)
- Retry messages visible in normal CLI output via print() per locked decision
- 41 total tests across test_resilience.py and test_harvest_agent.py, all passing

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: Failing tests for unified retry** - `da6f2d8` (test)
2. **Task 1 GREEN: Unified retry implementation** - `970f4f8` (feat)
3. **Task 2 RED: Failing tests for version persistence and usage** - `070c68d` (test)
4. **Task 2 GREEN: Version fix and usage accumulation** - `c2cf3c2` (feat)

## Files Created/Modified
- `src/skill_builder/resilience.py` - Added _is_retryable_any, _make_retry_callback, api_retry_any
- `src/skill_builder/harvest/firecrawl_strategy.py` - AsyncRetrying wrapper for async crawl
- `src/skill_builder/harvest/exa_strategy.py` - @api_retry_any on sync helper passed to to_thread
- `src/skill_builder/harvest/tavily_strategy.py` - @api_retry_any on sync helper passed to to_thread
- `src/skill_builder/harvest/github_strategy.py` - _httpx_get_with_retry for all httpx GET calls
- `src/skill_builder/agents/harvest.py` - enumerate fix for version detection, usage accumulation
- `tests/test_resilience.py` - TestUnifiedRetry (18 tests), TestRetryVisibility (1 test)
- `tests/test_harvest_agent.py` - TestVersionPersistence (3 tests), TestUsageAccumulation (2 tests)

## Decisions Made
- Used unified _is_retryable_any covering all SDKs in one function rather than per-SDK wrappers -- simpler, less code duplication
- Did NOT catch generic ValueError from Exa -- per research, transient Exa failures manifest as requests.ConnectionError/Timeout which are already covered
- Retry callback uses print() for user visibility plus logger.warning() for structured logging
- Usage accumulation uses getattr pattern to avoid modifying Pydantic model definitions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Pre-existing test failure:** `tests/test_tracing.py::TestTracingIntegration::test_traceable_agent_applied_to_run` was already failing before Plan 01 execution. It expects tracing wiring in conductor.py which is Plan 02/03 scope. Logged to deferred-items.md. Does not affect Plan 01 work.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Retry infrastructure is wired to all strategy functions -- ready for production use
- HarvestAgent usage accumulation pattern established -- Plan 02 can wire conductor budget recording using the same getattr(_usage_meta) pattern
- Version detection now correctly persists on HarvestPage -- downstream agents see accurate version data

## Self-Check: PASSED

- All 8 modified files verified on disk
- All 4 commits verified in git history (da6f2d8, 970f4f8, 070c68d, c2cf3c2)
- Key content artifacts verified: _is_retryable_any, api_retry_any, retry wrappers, enumerate, _usage_meta

---
*Phase: 04-integration-wiring*
*Completed: 2026-03-05*
