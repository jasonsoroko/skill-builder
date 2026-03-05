# Phase 1: Foundation - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the conductor backbone that drives skill-building runs end-to-end. Includes the deterministic state machine, Pydantic data models, checkpoint persistence, Click CLI scaffold, LangSmith tracing integration, and resilience patterns (backoff, budget cap). Phase-specific agents are stubs — real agents come in Phases 2 and 3.

</domain>

<decisions>
## Implementation Decisions

### Skill Brief Schema
- URLs are typed by source: `{"url": "...", "type": "docs|github|api_schema|blog"}`. Content router still validates at harvest time but gets a hint.
- Strict validation with good errors: required fields fail fast with specific messages, optional fields get sensible defaults with a note about what was defaulted.
- `required_capabilities` are free-text strings: `["authentication", "batch operations"]`. Gap Analyzer interprets them semantically.
- Ship an `examples/exa-tavily-firecrawl.json` as the first target skill brief. Doubles as documentation and smoke test.

### CLI Command Structure
- Single command: `skill-builder build brief.json [--dry-run] [--resume] [--verbose] [--budget N] [--force]`. One thing the tool does.
- Normal output: phase banners + status lines. Print phase transitions with timing: `[harvest] Starting... [harvest] Complete (12s, 8 pages)`.
- `--verbose` adds agent-level detail: which agent is running, what it received/returned (truncated), per-agent timing.
- `--dry-run` outputs a fetch plan table + cost estimate: URLs to crawl, searches to run, agents to invoke, estimated token usage and dollar cost per phase.

### Checkpoint & Resume UX
- State files live in `.skill-builder/state/` in CWD (colocated with where you run the tool). Gitignore it.
- Resume shows a one-line summary: "Resuming 'exa-tavily-firecrawl' from [synthesis] (harvest complete, 14 pages extracted). Continuing..."
- `--resume` is explicit — user must pass the flag. Without it, a fresh run starts.
- If state exists and user runs without `--resume` or `--force`: warn and exit. "State exists for 'exa-tavily-firecrawl'. Use --resume to continue or --force to start fresh."

### Token Budget Behavior
- Default global budget: $25 (overridable via `--budget`). Covers typical runs with feedback loops.
- When exceeded: finish current agent (don't waste in-flight work), then halt with clear message showing spend vs budget. State is checkpointed so user can resume with higher budget.
- Tracked via local token counter from Anthropic API response `usage` fields. LangSmith is for observability/reporting only — budget enforcement is real-time and local.
- Budget covers Anthropic tokens only. External API costs (Exa, Tavily, Firecrawl) are excluded — they're pay-per-call with known fixed costs.

### Claude's Discretion
- Exact Pydantic model field names and nesting
- State machine implementation pattern (enum-based, class-based, etc.)
- LangSmith @traceable wrapper implementation details
- Tenacity retry configuration specifics (initial wait, max wait, jitter)
- Logging framework choice (stdlib logging, loguru, structlog)
- Internal error handling patterns

</decisions>

<specifics>
## Specific Ideas

- The example brief should be for Exa + Tavily + Firecrawl (the first target skill and a meta-test of the tool itself)
- Phase banners should feel clean and informative — not noisy. Think `uv` or `ruff` output style.
- The tool name is `skill-builder` — single command, no subcommands

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — Phase 1 establishes all patterns

### Integration Points
- pyproject.toml will define the `skill-builder` CLI entry point via Click
- .env file for API keys (ANTHROPIC_API_KEY, LANGSMITH_API_KEY, EXA_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-05*
