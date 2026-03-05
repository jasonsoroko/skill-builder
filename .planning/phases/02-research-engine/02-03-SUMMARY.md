---
phase: 02-research-engine
plan: 03
subsystem: agents
tags: [anthropic, messages-parse, pydantic, structured-output, adaptive-thinking, opus, sonnet]

# Dependency graph
requires:
  - phase: 02-research-engine (plan 01)
    provides: "Pydantic models for synthesis (CategorizedResearch, GapReport, KnowledgeModel) and harvest (HarvestResult)"
  - phase: 02-research-engine (plan 02)
    provides: "HarvestAgent, extraction strategies, search query generation"
provides:
  - "OrganizerAgent -- Sonnet + messages.parse for dynamic CategorizedResearch with source attribution"
  - "GapAnalyzerAgent -- Opus + adaptive thinking + messages.parse for GapReport with capability checking"
  - "LearnerAgent -- Sonnet + messages.parse for complete KnowledgeModel extraction"
  - "Conductor with focused kwargs dispatch and real Phase 2 agents wired in"
affects: [03-output-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "messages.parse(output_format=PydanticModel) for all synthesis agents (SYNTH-06)"
    - "Adaptive thinking with output_format (not tool_choice) for Opus agents"
    - "_build_kwargs helper for focused agent dispatch per phase"
    - "Autouse fixture pattern for CLI test stub isolation"

key-files:
  created:
    - src/skill_builder/agents/organizer.py
    - src/skill_builder/agents/gap_analyzer.py
    - src/skill_builder/agents/learner.py
    - tests/test_organizer_agent.py
    - tests/test_gap_analyzer_agent.py
    - tests/test_learner_agent.py
  modified:
    - src/skill_builder/agents/__init__.py
    - src/skill_builder/conductor.py
    - tests/test_conductor.py
    - tests/test_cli.py

key-decisions:
  - "System prompt in each agent uses dedicated _SYSTEM_PROMPT constant (not inline) for readability"
  - "Conductor tests updated to explicitly pass stub_agents to avoid real API calls from _default_agents"
  - "CLI tests use autouse fixture patching _default_agents rather than per-test monkeypatch"
  - "Dict identity assertions changed to equality in conductor kwargs tests (Pydantic re-creates dicts)"

patterns-established:
  - "Synthesis agent pattern: __init__(client=None), run(**kwargs) -> PydanticModel, reconstruct typed input from dict, build prompt, call messages.parse"
  - "_build_kwargs(phase, state) centralizes kwargs dispatch in conductor"

requirements-completed: [SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04, SYNTH-05, SYNTH-06]

# Metrics
duration: 7min
completed: 2026-03-05
---

# Phase 2 Plan 3: Synthesis Agents & Conductor Wiring Summary

**Three synthesis agents (Organizer, Gap Analyzer, Learner) using messages.parse with Pydantic output, plus conductor rewired with focused kwargs dispatch and real Phase 2 agents**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-05T17:14:43Z
- **Completed:** 2026-03-05T17:21:51Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- OrganizerAgent produces dynamic CategorizedResearch with source attribution using Sonnet
- GapAnalyzerAgent uses Opus with adaptive thinking to check every required capability (SYNTH-04), logs warning on max_tokens truncation
- LearnerAgent distills complete KnowledgeModel from organized research using Sonnet
- All agents enforce Pydantic-validated output via messages.parse(output_format=Model) (SYNTH-06)
- Conductor passes focused kwargs (brief, raw_harvest, categorized_research, etc.) to each agent per phase
- _default_agents returns real agents for Phase 2, stubs for Phase 3
- 211 tests pass (21 new synthesis agent tests + 7 new conductor tests), zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Synthesis agents (RED)** - `0c84bfe` (test)
2. **Task 1: Synthesis agents (GREEN)** - `44ab42d` (feat)
3. **Task 2: Wire real agents into conductor** - `403fcbd` (feat)

_Note: TDD task had RED+GREEN commits. Lint fixes folded into Task 2 commit._

## Files Created/Modified
- `src/skill_builder/agents/organizer.py` - OrganizerAgent with Sonnet + messages.parse for CategorizedResearch
- `src/skill_builder/agents/gap_analyzer.py` - GapAnalyzerAgent with Opus + adaptive thinking for GapReport
- `src/skill_builder/agents/learner.py` - LearnerAgent with Sonnet + messages.parse for KnowledgeModel
- `src/skill_builder/agents/__init__.py` - Added real agent exports alongside stubs
- `src/skill_builder/conductor.py` - _default_agents uses real agents, _build_kwargs for focused dispatch
- `tests/test_organizer_agent.py` - 7 tests covering protocol, prompt content, model config, warnings
- `tests/test_gap_analyzer_agent.py` - 9 tests covering sufficient/insufficient, SYNTH-04, adaptive thinking
- `tests/test_learner_agent.py` - 5 tests covering protocol, field population, model config
- `tests/test_conductor.py` - Updated fixture + 7 new tests for kwargs dispatch and default agents
- `tests/test_cli.py` - Added autouse _default_agents stub fixture

## Decisions Made
- System prompts as module-level constants for readability and potential reuse
- Conductor tests explicitly pass stub_agents fixture instead of relying on _default_agents (avoids test coupling to real agent constructors that need API keys)
- CLI tests use autouse fixture to patch _default_agents globally rather than per-test monkeypatching
- Used equality checks (not identity) for dict kwargs assertions since Pydantic may re-create dict objects

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed conductor tests using _default_agents with real agents**
- **Found during:** Task 2 (Conductor wiring)
- **Issue:** Existing conductor and CLI tests called Conductor() without agents kwarg, which now uses real agents that need API keys
- **Fix:** Added stub_agents fixture to conductor tests; added autouse _default_agents patch to CLI tests
- **Files modified:** tests/test_conductor.py, tests/test_cli.py
- **Verification:** All 211 tests pass
- **Committed in:** 403fcbd (Task 2 commit)

**2. [Rule 1 - Bug] Fixed lint errors (unused imports)**
- **Found during:** Task 2 verification
- **Issue:** Unused `json` import in organizer.py, unused `pytest` and `call` imports in test files
- **Fix:** Removed unused imports
- **Files modified:** src/skill_builder/agents/organizer.py, tests/test_organizer_agent.py, tests/test_learner_agent.py
- **Verification:** `ruff check` passes cleanly
- **Committed in:** 403fcbd (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for test correctness after _default_agents change. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 (Research Engine) is now complete: all harvest and synthesis agents implemented
- Phase 3 (Output Pipeline) can proceed: mapper, documenter, validator, packager agents remain as stubs
- KnowledgeModel output from Learner feeds directly into Phase 3 mapper agent
- Conductor's _build_kwargs already defines kwargs for all Phase 3 phases

---
*Phase: 02-research-engine*
*Completed: 2026-03-05*
