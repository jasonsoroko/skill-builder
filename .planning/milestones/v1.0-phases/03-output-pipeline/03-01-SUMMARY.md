---
phase: 03-output-pipeline
plan: 01
subsystem: agents
tags: [anthropic, sonnet, pydantic, ast, evaluators, mapper, documenter]

# Dependency graph
requires:
  - phase: 02-research-engine
    provides: KnowledgeModel from LearnerAgent, established Sonnet messages.parse pattern
provides:
  - MapperAgent producing SkillDraft via Sonnet messages.parse
  - DocumenterAgent producing SetupDraft via Sonnet messages.parse
  - check_compactness heuristic evaluator (line count <= 500)
  - check_syntax heuristic evaluator (ast.parse Python blocks)
  - SkillDraft extended with optional reference_files field
affects: [03-02 ValidatorAgent, 03-03 PackagerAgent, conductor integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [production agent pattern (Mapper/Documenter), heuristic evaluator pattern (pure function -> EvaluationDimension)]

key-files:
  created:
    - src/skill_builder/agents/mapper.py
    - src/skill_builder/agents/documenter.py
    - src/skill_builder/evaluators/__init__.py
    - src/skill_builder/evaluators/compactness.py
    - src/skill_builder/evaluators/syntax.py
    - tests/test_mapper_agent.py
    - tests/test_documenter_agent.py
    - tests/test_evaluators.py
  modified:
    - src/skill_builder/models/production.py

key-decisions:
  - "System prompts as module-level _SYSTEM_PROMPT constants (consistent with Phase 2 convention)"
  - "Heuristic evaluators are pure functions with no LLM dependencies, enabling fast fail-fast gating"
  - "SkillDraft.reference_files is optional (None default) for backward compatibility with existing usage"

patterns-established:
  - "Production agent pattern: __init__(client=None), run(**kwargs) -> Model, _build_prompt() method, messages.parse with output_format"
  - "Heuristic evaluator pattern: pure function(content: str) -> EvaluationDimension, no external deps"
  - "Re-production feedback: failed_dimensions list[dict] with name + feedback, appended as FIX THESE ISSUES section"

requirements-completed: [PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, VAL-01, VAL-02]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 03 Plan 01: Production Agents + Heuristic Evaluators Summary

**MapperAgent and DocumenterAgent using Sonnet messages.parse, plus compactness and syntax heuristic evaluators with ast.parse validation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T20:10:35Z
- **Completed:** 2026-03-05T20:14:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 9

## Accomplishments
- MapperAgent produces SkillDraft with 500-line budget enforcement, YAML frontmatter with pushy trigger, worked examples for all canonical use cases, DO/DON'T section, and reference extraction support
- DocumenterAgent produces SetupDraft with prerequisites, API keys, quick start, and top 3 troubleshooting tips
- SkillDraft model extended with backward-compatible reference_files field (dict[str, str] | None)
- check_compactness pure-Python evaluator with line count scoring
- check_syntax validates only Python code blocks via ast.parse, skipping bash/json/yaml
- MapperAgent handles failed_dimensions for re-production feedback loop (only failed dimensions with feedback)
- 35 new tests, 246 total suite green with 0 regressions

## Task Commits

Each task was committed atomically (TDD cycle):

1. **Task 1 RED: Failing tests for mapper, documenter, evaluators** - `aef67b2` (test)
2. **Task 1 GREEN: Implement mapper, documenter, evaluators** - `8c8a8e4` (feat)

**Plan metadata:** `8bf2afd` (docs: complete plan)

_Note: TDD task with RED -> GREEN cycle. No REFACTOR needed -- implementation follows established patterns._

## Files Created/Modified
- `src/skill_builder/models/production.py` - Extended SkillDraft with reference_files field
- `src/skill_builder/agents/mapper.py` - MapperAgent: KnowledgeModel -> SkillDraft via Sonnet
- `src/skill_builder/agents/documenter.py` - DocumenterAgent: KnowledgeModel -> SetupDraft via Sonnet
- `src/skill_builder/evaluators/__init__.py` - Package init exporting check_compactness, check_syntax
- `src/skill_builder/evaluators/compactness.py` - Line count heuristic evaluator
- `src/skill_builder/evaluators/syntax.py` - Python syntax validator via ast.parse
- `tests/test_mapper_agent.py` - 13 tests covering protocol, run behavior, prompts
- `tests/test_documenter_agent.py` - 9 tests covering protocol, run behavior, prompts
- `tests/test_evaluators.py` - 13 tests covering compactness and syntax evaluators

## Decisions Made
- System prompts as module-level `_SYSTEM_PROMPT` constants (consistent with Phase 2 convention)
- Heuristic evaluators are pure functions returning EvaluationDimension -- no classes, no LLM calls
- SkillDraft.reference_files defaults to None for backward compatibility with all existing tests and code
- MapperAgent uses max_tokens=8192 per plan specification; DocumenterAgent uses 4096 (simpler output)
- Failed dimensions feedback uses "FIX THESE ISSUES" section header in prompt for clarity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- MapperAgent and DocumenterAgent ready for conductor wiring (Plan 02 will create ValidatorAgent and wire into conductor)
- check_compactness and check_syntax ready for fail-fast gating in ValidatorAgent
- SkillDraft.reference_files ready for PackagerAgent to write extracted reference files (Plan 03)

## Self-Check: PASSED

- All 9 files verified present on disk
- Both commits (aef67b2, 8c8a8e4) verified in git log
- 246/246 tests passing

---
*Phase: 03-output-pipeline*
*Completed: 2026-03-05*
