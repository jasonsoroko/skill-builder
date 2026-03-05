# Phase 3: Output Pipeline - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Take a KnowledgeModel and produce a validated, packaged `.skill` file. Includes drafting SKILL.md and SETUP.md via production agents, running heuristic and LLM-as-judge evaluators with feedback routing, assembling the final package for the specified deploy target, and adding Rich CLI progress throughout the entire pipeline. Replaces all Phase 3 stub agents with real implementations.

</domain>

<decisions>
## Implementation Decisions

### SKILL.md Drafting
- Worked examples must be complete runnable snippets: imports, setup, execution, output handling. Copy-pasteable.
- Include an explicit DO/DON'T (or "Important Rules") section derived from gotchas and anti-patterns in the KnowledgeModel. Tell Claude what to avoid.
- Reference section extraction is Claude's discretion -- Mapper decides what to pull into references/ based on content and the 500-line budget.
- Trigger description design is Claude's discretion -- Mapper crafts the trigger based on what it learned from the KnowledgeModel (trigger phrases, tool category, target use case).

### Evaluator Architecture
- Single ValidatorAgent runs all 5 evaluators internally and returns a unified EvaluationResult. Matches existing stub shape.
- Heuristic evaluators (compactness, syntax) run first and fail-fast: if either fails, skip the 3 expensive Opus LLM-as-judge calls. Saves cost on obvious failures.
- Syntax evaluator validates Python code blocks only (via ast.parse). Skip bash, JSON, YAML, and other language blocks.
- The 3 LLM-as-judge evaluators (API accuracy, completeness, trigger quality) run in parallel via asyncio.gather. They're independent of each other.
- When validation fails and routes back to production, pass only the failed dimensions with their feedback strings. Mapper sees exactly what to fix without noise from passing dimensions.

### Package Format & Deploy Targets
- Output folder structure: SKILL.md and SETUP.md at root, with references/, scripts/, and assets/ subdirectories. LICENSE.txt (MIT) at root.
- Deploy targets differ by output path:
  - `repo`: writes to `.claude/skills/{tool_name}/` -- already in repo scope
  - `user`: writes to `~/.claude/skills/{tool_name}/` -- available in all projects
  - `package`: writes to `.skill-builder/output/{tool_name}/` -- standalone, user copies manually
- After packaging, print manual verification steps: open Claude Code, ask a trigger question, check the skill activates. List output files with line counts.

### Rich CLI Progress
- Use Rich Live display with a status panel: current phase, active agent, iteration count, elapsed time. Updates in-place during TTY sessions.
- Auto-detect non-TTY (CI, piped output) and degrade to plain text log lines. This is Rich's default behavior.
- `--verbose` adds budget summary at phase boundaries: cumulative spend vs budget with percentage. Per-agent token details stay in LangSmith.
- Final run summary panel after packaging: total time, total cost, evaluator scores, feedback loop counts, output path, verification instructions. One glanceable block.

### Claude's Discretion
- Mapper's approach to SKILL.md section ordering and structure
- Mapper's reference extraction strategy (what goes to references/ vs stays inline)
- Trigger description wording and aggressiveness
- Documenter's SETUP.md structure and troubleshooting tip selection
- Rich panel layout and styling details
- How the ValidatorAgent passes organized research to the API accuracy evaluator
- How to bridge sync/async for parallel LLM evaluator calls within ValidatorAgent

</decisions>

<specifics>
## Specific Ideas

- Evaluator scores should display as `9/10 PASS` or `4/10 FAIL` -- clean, scannable
- The final summary panel should feel like a build receipt: time, cost, scores, output path, next step
- Budget display at phase boundaries: `$5.82 / $25.00 (23.3%)`
- The verification instructions should be specific enough to actually test: "Ask Claude 'How do I use Exa for search?'" not just "check it works"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SkillDraft` model (content, line_count, has_frontmatter): production.py -- ready to use for Mapper output
- `SetupDraft` model (content, has_prerequisites, has_quick_start): production.py -- ready to use for Documenter output
- `EvaluationDimension` model (name, score, feedback, passed): evaluation.py -- ready to use for individual evaluator results
- `EvaluationResult` model (dimensions, overall_pass, iteration): evaluation.py -- ready to use for unified ValidatorAgent output
- Stub agents (StubMapperAgent, StubDocumenterAgent, StubValidatorAgent, StubPackagerAgent): show expected I/O shapes
- `BaseAgent` Protocol (run(**kwargs) -> BaseModel | dict): real agents must conform to this
- `TokenBudget` class (budget.py): tracks cumulative spend for budget summary display
- `@traceable` LangSmith decorator pattern (tracing.py): for all Anthropic calls in evaluators

### Established Patterns
- Conductor dispatches agents via `_PHASE_AGENT_MAP` dict -- real agents replace stubs
- `_resolve_eval_transition()` handles the validation feedback loop -- already works with EvaluationResult
- Phase 2 used `asyncio.to_thread()` for sync-to-async bridging -- reuse for parallel LLM evaluator calls
- System prompts as module-level `_SYSTEM_PROMPT` constants (Phase 2 convention)
- `_build_kwargs(phase, state)` centralizes focused kwargs dispatch in conductor

### Integration Points
- Real agents replace stubs in `conductor.py` `_default_agents()` function (mapper, documenter, validator, packager)
- Conductor already handles production -> validation -> packaging transitions
- Rich output integrates with existing CLI entry point in `cli.py`
- Checkpoint persistence already handles Phase 3 state fields (skill_draft, setup_draft, evaluation_result, package_path)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-output-pipeline*
*Context gathered: 2026-03-05*
