# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 -- MVP

**Shipped:** 2026-03-05
**Phases:** 4 | **Plans:** 11 | **Sessions:** ~4

### What Was Built
- Deterministic conductor state machine driving 9 agents through 14 pipeline phases with feedback loops
- Multi-source parallel harvest (Firecrawl, GitHub, Exa, Tavily) with dedup, version detection, and gap analysis
- Production pipeline: Mapper/Documenter agents, 5 evaluators (2 heuristic + 3 Opus LLM-as-judge), PackagerAgent
- Full observability: LangSmith tracing with dynamic metadata, budget enforcement, exponential backoff retry on all SDKs
- Rich CLI with progress display, TTY fallback, and build receipt summary panel

### What Worked
- TDD (RED-GREEN) cycle kept every plan focused and prevented regressions -- 342 tests with 0 failures at completion
- Coarse roadmap granularity (3 core phases + 1 gap-closure) -- each phase was independently verifiable and naturally followed the pipeline data flow
- Stub agents in Phase 1 allowed full conductor testing before any real agent existed -- feedback loop logic was solid before Phase 2
- messages.parse with Pydantic output_format pattern -- simple, type-safe, consistent across all 8 real agents
- Milestone audit caught 4 real gaps (CORE-08, RES-01, OBS-02, HARV-08) that would have shipped unfinished

### What Was Inefficient
- Nyquist validation documents were created but never finalized (all 4 phases show nyquist_compliant: false) -- the validation strategy existed but sign-off wasn't integrated into the execution flow
- Phase 1 assigned 15 requirements including some that couldn't be fully satisfied until integration wiring (CORE-08, OBS-02, RES-01) -- these had to be re-mapped to Phase 4
- Version detection bug (loop variable rebinding) wasn't caught until Phase 4 audit despite existing tests -- test coverage for version persistence on HarvestPage objects was missing

### Patterns Established
- Agent pattern: `__init__(client=None)`, `run(**kwargs) -> PydanticModel`, `_build_prompt()`, `messages.parse(output_format=Model)`
- Heuristic evaluator: pure function returning `EvaluationDimension`, no LLM needed
- LLM evaluator: async function with programmatic `passed = score >= 7` override
- `_usage_meta` dynamic attribute pattern for usage tracking without schema changes
- `_build_kwargs(phase, state)` for focused agent dispatch in conductor
- Sync SDK -> `asyncio.to_thread()` for safe parallel execution

### Key Lessons
1. Assign requirements to the phase where they'll actually be wired end-to-end, not just where infrastructure is created
2. Milestone audits before completion are high-value -- they caught 4 gaps that would have been tech debt forever
3. Pure-function heuristic evaluators as fail-fast gates save significant cost by avoiding unnecessary LLM calls
4. Don't trust LLM threshold judgment -- programmatic score override is essential for reliable validation

### Cost Observations
- Model mix: ~70% Sonnet, ~30% Opus (Opus only for Gap Analyzer + 3 LLM evaluators)
- Sessions: ~4 Claude Code sessions across 1 day
- Notable: Entire v1.0 built in ~1 hour of execution time across 11 plans (avg 5.5 min/plan)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 4 | Established TDD, milestone audit, coarse granularity |

### Cumulative Quality

| Milestone | Tests | Tech Debt Items | Plans |
|-----------|-------|-----------------|-------|
| v1.0 | 342 | 5 (info-level) | 11 |

### Top Lessons (Verified Across Milestones)

1. Milestone audits catch real gaps -- always run before completion
2. TDD keeps plan execution focused and prevents regressions
