---
phase: 01-foundation
plan: 03
subsystem: conductor
tags: [state-machine, click-cli, pipeline, checkpoint, resume, budget, dry-run, feedback-loops]

# Dependency graph
requires:
  - phase: 01-foundation/01
    provides: Pydantic data models (PipelinePhase, PipelineState, SkillBrief, GapReport, EvaluationResult)
  - phase: 01-foundation/02
    provides: CheckpointStore, TokenBudget, stub agents, BaseAgent protocol
provides:
  - Conductor state machine driving all pipeline phases end-to-end
  - Feedback loops for gap analysis (max 2 iterations) and validation (max 2 iterations)
  - Checkpoint persistence after every phase transition with resume support
  - Budget enforcement halting pipeline when exceeded
  - Click CLI entry point with --dry-run, --resume, --verbose, --budget, --force options
  - State clash detection (warn and exit without --resume/--force)
  - Dry-run mode with fetch plan table and cost estimate
affects: [02-research-engine, 03-output-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [conductor-transition-table, conditional-feedback-loops, phase-banner-output, cli-state-clash-detection, dry-run-cost-estimate]

key-files:
  created:
    - src/skill_builder/conductor.py
    - src/skill_builder/cli.py
    - tests/test_conductor.py
    - tests/test_cli.py
  modified: []

key-decisions:
  - "Checkpoint semantics: phase=X means phase X already completed (checkpoint saved AFTER agent runs); resume continues from next phase"
  - "Used temporary _last_gap_report and _last_eval_result attributes on state for transition logic (avoids re-parsing stored dicts)"
  - "Single command CLI (skill-builder BRIEF) not subcommand (skill-builder build BRIEF) per Click @click.command() pattern"
  - "Dry-run uses stub-based cost estimates ($0.27 for 13 phases at Sonnet pricing); real costs will vary in Phase 2+"

patterns-established:
  - "Conductor: static TRANSITION_TABLE dict with _CONDITIONAL sentinel for feedback loops"
  - "Conductor: _PHASE_AGENT_MAP connects phases to agent dict keys"
  - "Conductor: _store_result dispatches agent output to correct PipelineState field"
  - "CLI: CheckpointStore(_STATE_DIR) with relative path for CWD-local state"
  - "CLI: SystemExit(1) for state clash, not click.Abort()"
  - "Phase banners: [phase_value] Starting... / [phase_value] Complete (Xs)"

requirements-completed: [CORE-02, CORE-03, CORE-04, CORE-06, CORE-07, CORE-09, RES-03]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 1 Plan 03: Conductor State Machine and CLI Summary

**Deterministic state machine with gap/validation feedback loops (max 2 each), checkpoint-at-every-boundary persistence, and Click CLI with dry-run, resume, force, budget override -- 90 tests passing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T16:04:00Z
- **Completed:** 2026-03-05T16:09:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Conductor drives stub agents through all 10+ phases from INITIALIZED to COMPLETE with clean phase banners
- Gap analysis and validation feedback loops work correctly with hard caps at 2 iterations each
- Checkpoint persistence saves state after every phase transition; resume skips completed phases
- Budget exceeded halts gracefully after current agent, saving state for resume with higher budget
- Agent exceptions transition to FAILED with error message saved in state
- Click CLI accepts all options (--dry-run, --resume, --verbose, --budget, --force) per user decisions
- State clash detection warns and exits when state exists without --resume/--force
- Dry-run prints fetch plan with URLs, pipeline phases, and cost estimate using Sonnet pricing
- Full test suite at 90 tests (25 new: 14 conductor + 11 CLI)

## Task Commits

Each task was committed atomically:

1. **Task 1: Conductor state machine (TDD)**
   - `3ed1f40` (test): add failing tests for conductor state machine (RED)
   - `e9878b6` (feat): implement conductor state machine with feedback loops (GREEN)

2. **Task 2: Click CLI entry point (TDD)**
   - `271a985` (test): add failing tests for Click CLI entry point (RED)
   - `02c0919` (feat): implement Click CLI with dry-run and state clash detection (GREEN)

## Files Created/Modified
- `src/skill_builder/conductor.py` - Conductor class with TRANSITION_TABLE, feedback loops, budget enforcement, and phase banners
- `src/skill_builder/cli.py` - Click CLI entry point with dry-run, resume, force, budget, and verbose options
- `tests/test_conductor.py` - 14 tests: happy path, gap loop, validation loop, checkpoint, resume, budget, failed state, transition completeness
- `tests/test_cli.py` - 11 tests: basic invocation, dry-run, resume, state clash, force, budget, verbose, missing file, help

## Decisions Made
- Checkpoint semantics: `phase=X` means phase X already completed; resume continues from the next phase (not re-running X). This matches the save-after-run pattern.
- Used temporary `_last_gap_report` and `_last_eval_result` attributes on PipelineState for transition logic to avoid re-constructing Pydantic models from stored dicts.
- Implemented as single command (`skill-builder BRIEF`) via `@click.command()`, not as subcommand (`skill-builder build BRIEF`). The pyproject.toml entry point maps `skill-builder` directly to `cli:main`.
- Dry-run cost estimates use stub-based profiles (2000 input + 1000 output tokens per phase at Sonnet $3/$15 pricing). Real costs will vary significantly in Phase 2+.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed resume test expecting wrong phase semantics**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test expected organizer agent to run when resuming from phase=ORGANIZING, but checkpoint semantics mean ORGANIZING already completed
- **Fix:** Updated test to verify gap_analyzer runs instead (first phase after ORGANIZING), and that intake/harvest/organizer are all skipped
- **Files modified:** `tests/test_conductor.py`
- **Verification:** All 14 conductor tests pass
- **Committed in:** `e9878b6` (part of GREEN commit)

**2. [Rule 3 - Blocking] Fixed ruff lint errors (unused imports, import sorting, line length)**
- **Found during:** Task 1 and Task 2 (GREEN phases)
- **Issue:** Unused imports (MagicMock, sys, Any), unused variable (expected_phases), import sorting, line too long
- **Fix:** Removed unused imports/variables, ran ruff --fix for import sorting, shortened help string
- **Files modified:** `tests/test_conductor.py`, `src/skill_builder/cli.py`, `tests/test_cli.py`
- **Verification:** `ruff check src/ tests/` passes with zero errors
- **Committed in:** `e9878b6` and `02c0919` (part of GREEN commits)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correct semantics and clean lint. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 Foundation is now complete (all 3 plans executed)
- Full pipeline runs end-to-end with stub agents: 90 tests pass, CLI works, dry-run works
- Ready for Phase 2 (Research Engine) to replace stub agents with real implementations
- Conductor will accept real agents via the agents dict parameter
- CheckpointStore, TokenBudget, and tracing are independently tested and wired in

## Self-Check: PASSED

All 4 files verified present. All 4 commits (3ed1f40, e9878b6, 271a985, 02c0919) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-05*
