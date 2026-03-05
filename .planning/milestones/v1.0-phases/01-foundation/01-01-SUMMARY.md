---
phase: 01-foundation
plan: 01
subsystem: models
tags: [pydantic, python, data-models, validation, json-serialization]

# Dependency graph
requires:
  - phase: none
    provides: greenfield project
provides:
  - Pydantic data models for all pipeline phases (brief, state, harvest, synthesis, production, evaluation)
  - SkillBrief input validation with typed URLs and computed slug
  - PipelineState with StrEnum phases and JSON round-trip support
  - Example skill brief (exa-tavily-firecrawl) as fixture and documentation
  - Test infrastructure (conftest fixtures, 19 passing tests)
  - Project scaffold (pyproject.toml, .gitignore, dev dependencies)
affects: [01-foundation, 02-research-engine, 03-output-pipeline]

# Tech tracking
tech-stack:
  added: [pydantic>=2.12, click>=8.3, anthropic>=0.84, langsmith>=0.7, tenacity>=9.1, pytest>=8.0, ruff>=0.15, mypy>=1.13, hatchling>=1.25]
  patterns: [pydantic-v2-models, strenum-phases, computed-field-slug, model-validate-json-roundtrip]

key-files:
  created:
    - pyproject.toml
    - src/skill_builder/__init__.py
    - src/skill_builder/models/__init__.py
    - src/skill_builder/models/brief.py
    - src/skill_builder/models/state.py
    - src/skill_builder/models/harvest.py
    - src/skill_builder/models/synthesis.py
    - src/skill_builder/models/production.py
    - src/skill_builder/models/evaluation.py
    - examples/exa-tavily-firecrawl.json
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_models.py
    - .gitignore
    - .python-version
  modified: []

key-decisions:
  - "Used StrEnum instead of str+Enum mixin for PipelinePhase (modern Python 3.12+ pattern, ruff UP042 compliance)"
  - "Used computed_field for brief_name slug derivation (derived property, not stored in JSON)"
  - "Used datetime.UTC instead of timezone.utc (Python 3.12+ alias, ruff UP017 compliance)"
  - "Used dict | None for phase output placeholders in PipelineState (typed models will replace in Phase 2+)"

patterns-established:
  - "Pydantic v2 models with str | None = None for optional fields"
  - "StrEnum for JSON-serializable enums"
  - "model_validate_json / model_dump_json for serialization round-trip"
  - "Field(min_length=1) for required non-empty strings"
  - "Field(default_factory=...) for mutable defaults and datetime"
  - "computed_field for derived properties"

requirements-completed: [CORE-01]

# Metrics
duration: 4min
completed: 2026-03-05
---

# Phase 1 Plan 01: Project Scaffold and Data Models Summary

**Pydantic v2 data models for all 6 pipeline phases with StrEnum state machine, typed URL validation, JSON round-trip serialization, and 19 passing tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T15:46:48Z
- **Completed:** 2026-03-05T15:51:20Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- All 7 model files implemented with full Pydantic v2 type contracts for the entire pipeline
- SkillBrief validates typed seed URLs, rejects malformed input with specific error messages, and derives a slugified brief_name
- PipelineState round-trips through JSON preserving datetime and StrEnum fields (critical for checkpoint persistence)
- Example brief for exa-tavily-firecrawl validates successfully as first target skill
- 19 model tests covering valid/invalid brief, state round-trip, enum serialization, and all module exports

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold and Pydantic data models**
   - `2bda90a` (test): add failing tests for Pydantic data models (TDD RED)
   - `de6756c` (feat): implement Pydantic data models for pipeline contracts (TDD GREEN+REFACTOR)

2. **Task 2: Example skill brief and model completeness** - `612efe3` (feat)

## Files Created/Modified
- `pyproject.toml` - Project metadata, dependencies (click, pydantic, anthropic, langsmith, tenacity), dev deps, CLI entry point, pytest/ruff/mypy config
- `src/skill_builder/__init__.py` - Package init with __version__
- `src/skill_builder/models/__init__.py` - Re-exports all 14 primary model types
- `src/skill_builder/models/brief.py` - SeedUrl (typed URL) and SkillBrief (input contract with validation)
- `src/skill_builder/models/state.py` - PipelinePhase (StrEnum with 14 phases) and PipelineState (full pipeline state)
- `src/skill_builder/models/harvest.py` - HarvestPage and HarvestResult
- `src/skill_builder/models/synthesis.py` - ResearchCategory, CategorizedResearch, GapReport, KnowledgeModel
- `src/skill_builder/models/production.py` - SkillDraft and SetupDraft
- `src/skill_builder/models/evaluation.py` - EvaluationDimension (scored 1-10) and EvaluationResult
- `examples/exa-tavily-firecrawl.json` - First target skill brief with 5 typed URLs and 5 capabilities
- `tests/conftest.py` - Fixtures: sample_brief_dict, sample_brief_json, tmp_state_dir
- `tests/test_models.py` - 19 tests covering validation, round-trip, enum, and exports
- `.gitignore` - Python ignores plus .skill-builder/state/ checkpoint dir
- `.python-version` - Python 3.12

## Decisions Made
- Used `StrEnum` (Python 3.12+) instead of `str, Enum` mixin for cleaner code and ruff compliance
- Used `computed_field` for `brief_name` to keep it derived rather than stored in serialized JSON
- Used `datetime.UTC` alias (Python 3.12+) instead of `timezone.utc`
- Phase output fields in PipelineState are `dict | None` placeholders -- real typed models will replace these in Phase 2+

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff lint errors for modern Python patterns**
- **Found during:** Task 1 (REFACTOR phase)
- **Issue:** Ruff UP042 flagged `class PipelinePhase(str, Enum)` and UP017 flagged `timezone.utc`
- **Fix:** Changed to `StrEnum` and `datetime.UTC` (both Python 3.12+ features matching requires-python)
- **Files modified:** `src/skill_builder/models/state.py`
- **Verification:** `ruff check src/ tests/` passes with zero errors
- **Committed in:** `de6756c` (part of GREEN+REFACTOR commit)

**2. [Rule 3 - Blocking] Fixed test F401 lint errors for import verification test**
- **Found during:** Task 1 (REFACTOR phase)
- **Issue:** Ruff F401 flagged imports in test_models_init_reexports as unused
- **Fix:** Restructured test to use `hasattr()` checks on module namespace instead of direct imports
- **Files modified:** `tests/test_models.py`
- **Verification:** `ruff check tests/` passes, test still verifies all 14 exports
- **Committed in:** `de6756c` (part of GREEN+REFACTOR commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were necessary for clean lint. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All data models ready for Plan 02 (checkpoint store, budget tracker, tracing) to build on
- PipelineState JSON round-trip works, ready for CheckpointStore implementation
- Example brief ready for CLI smoke testing in Plan 03

## Self-Check: PASSED

All 15 files verified present. All 3 commits (2bda90a, de6756c, 612efe3) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-05*
