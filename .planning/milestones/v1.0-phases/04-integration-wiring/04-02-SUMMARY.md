---
phase: 04-integration-wiring
plan: 02
subsystem: observability
tags: [budget, tracing, langsmith, usage-metadata, token-tracking]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: TokenBudget, traceable_agent, BaseAgent Protocol
  - phase: 02-research-engine
    provides: Agent implementations (organizer, gap_analyzer, learner, harvest)
  - phase: 03-output-pipeline
    provides: Agent implementations (mapper, documenter, validator, packager)
provides:
  - Usage metadata (_usage_meta) attached to all LLM-calling agent results
  - Budget recording wired in conductor._run_phase
  - Dynamic tracing decoration on every agent.run() dispatch
  - Accumulated usage from ValidatorAgent's 3 parallel evaluators
affects: [conductor, budget-enforcement, langsmith-tracing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_usage_meta dict attached to Pydantic model results via type: ignore[attr-defined]"
    - "traceable_agent applied dynamically at dispatch time (not as static decorator)"
    - "Usage accumulation pattern for multi-call agents"

key-files:
  created: []
  modified:
    - src/skill_builder/conductor.py
    - src/skill_builder/agents/organizer.py
    - src/skill_builder/agents/gap_analyzer.py
    - src/skill_builder/agents/learner.py
    - src/skill_builder/agents/mapper.py
    - src/skill_builder/agents/documenter.py
    - src/skill_builder/agents/validator.py
    - src/skill_builder/evaluators/api_accuracy.py
    - src/skill_builder/evaluators/completeness.py
    - src/skill_builder/evaluators/trigger_quality.py
    - src/skill_builder/harvest/query_generator.py
    - src/skill_builder/harvest/saturation.py
    - tests/test_conductor.py
    - tests/test_tracing.py

key-decisions:
  - "Usage metadata attached as dynamic attribute (_usage_meta) on Pydantic result objects rather than as a Pydantic field -- avoids schema changes and serialization side effects"
  - "Tracing applied dynamically at dispatch time (not as static decorator on agent classes) for correct per-call metadata"
  - "Budget recording placed in conductor._run_phase after agent.run() returns -- centralized extraction point"
  - "ValidatorAgent accumulates usage from all 3 LLM evaluator EvaluationDimension results"

patterns-established:
  - "_usage_meta pattern: attach {model, input_tokens, output_tokens} dict as dynamic attribute on result"
  - "Conductor extracts _usage_meta via getattr(result, '_usage_meta', None) -- graceful when absent"
  - "Iteration metadata: gap_loop_count for harvest/gap phases, validation_loop_count for validation phases, 0 otherwise"

requirements-completed: [CORE-08, OBS-02]

# Metrics
duration: 6min
completed: 2026-03-05
---

# Phase 4 Plan 2: Budget Recording and Dynamic Tracing Summary

**Usage metadata wired across all 11 LLM-calling components, budget.record_usage() called in conductor, traceable_agent applied dynamically to every agent dispatch**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-05T22:24:59Z
- **Completed:** 2026-03-05T22:31:00Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- All 5 single-call agents and 5 sub-components (3 evaluators, query_generator, saturation) attach _usage_meta to their results
- ValidatorAgent accumulates usage from 3 parallel LLM evaluator calls
- Conductor extracts _usage_meta and calls budget.record_usage() after every agent dispatch
- Every agent.run() call wrapped with traceable_agent for LangSmith spans with phase/agent_name/iteration metadata
- 342 tests pass (34 new, 0 regressions from 308 baseline)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add usage metadata to all LLM-calling agents** - `38ad270` (test: RED) + `1485a1f` (feat: GREEN)
2. **Task 2: Wire dynamic tracing decoration in conductor** - `aa19a90` (test: RED) + `c233fb4` (feat: GREEN)

_Note: TDD tasks have RED (failing test) and GREEN (implementation) commits._

## Files Created/Modified
- `src/skill_builder/conductor.py` - Budget recording extraction and traceable_agent wrapping in _run_phase
- `src/skill_builder/agents/organizer.py` - _usage_meta attached to CategorizedResearch result
- `src/skill_builder/agents/gap_analyzer.py` - _usage_meta attached to GapReport result
- `src/skill_builder/agents/learner.py` - _usage_meta attached to KnowledgeModel result
- `src/skill_builder/agents/mapper.py` - _usage_meta attached to SkillDraft result
- `src/skill_builder/agents/documenter.py` - _usage_meta attached to SetupDraft result
- `src/skill_builder/agents/validator.py` - Accumulated _usage_meta from 3 evaluators on EvaluationResult
- `src/skill_builder/evaluators/api_accuracy.py` - _usage_meta on EvaluationDimension
- `src/skill_builder/evaluators/completeness.py` - _usage_meta on EvaluationDimension
- `src/skill_builder/evaluators/trigger_quality.py` - _usage_meta on EvaluationDimension
- `src/skill_builder/harvest/query_generator.py` - _usage_meta on GeneratedQueries (both functions)
- `src/skill_builder/harvest/saturation.py` - _usage_meta on SaturationResult
- `tests/test_conductor.py` - TestBudgetRecording class (4 tests)
- `tests/test_tracing.py` - TestTracingIntegration class (5 tests)

## Decisions Made
- Usage metadata attached as dynamic attribute (_usage_meta) on Pydantic result objects rather than as a Pydantic field -- avoids schema changes and serialization side effects
- Tracing applied dynamically at dispatch time (not as static decorator on agent classes) for correct per-call metadata with iteration counts
- Budget recording placed in conductor._run_phase after agent.run() returns -- centralized extraction point
- ValidatorAgent accumulates usage from all 3 LLM evaluator EvaluationDimension results into a single _usage_meta

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Linter (ruff with isort) removed the traceable_agent import on first application due to concurrent file modifications from Plan 04-01 -- re-applied and verified

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CORE-08 (budget enforcement) and OBS-02 (tracing metadata) requirements are now satisfied
- All Phase 4 integration wiring is complete when combined with Plan 04-01 (retry + version persistence)
- Full test suite passes (342 tests, 0 regressions)

## Self-Check: PASSED

- All 14 modified files exist on disk
- All 4 task commits verified (38ad270, 1485a1f, aa19a90, c233fb4)
- Full test suite: 342 passed, 0 failed

---
*Phase: 04-integration-wiring*
*Completed: 2026-03-05*
