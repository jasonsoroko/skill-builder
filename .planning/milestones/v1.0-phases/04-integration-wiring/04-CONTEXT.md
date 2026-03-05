# Phase 4: Integration Wiring - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire existing tested infrastructure (budget recording, retry decorators, tracing decorators) into production code so that budget enforcement halts on exceeded, all external API calls retry on transient failure, all agent runs emit LangSmith spans with metadata, and version detection persists on HarvestPage objects. This is a gap closure phase -- no new infrastructure, only wiring what exists.

</domain>

<decisions>
## Implementation Decisions

### Retry Visibility
- Retry attempts must be visible in normal CLI output, not just --verbose mode
- Show messages like "Retrying Firecrawl (attempt 2/5)..." so users see when something is going wrong
- This is a user-facing signal, not a debug detail

### Claude's Discretion
- Non-Anthropic retry strategy: whether to extend api_retry generically or create per-SDK wrappers (based on what exceptions each SDK actually raises)
- Retry timing: production-realistic vs fast defaults, considering this is a local Mac CLI tool
- Retry exhaustion handling: how to propagate failures given existing conductor error handling and checkpoint patterns
- Budget recording placement: centralized in conductor vs distributed inside agents (based on where response.usage is most accessible)
- Budget halt message verbosity: how much detail to show when budget is exceeded
- Budget scope: whether to track external API call counts alongside Anthropic token budget
- Budget check timing: before-and-after vs after-only, respecting the Phase 1 decision ("finish current agent, then halt")
- Tracing span structure: where to apply @traceable_agent for best LangSmith span hierarchy
- Version persistence verification: tracing the full data path vs verifying end-state

</decisions>

<specifics>
## Specific Ideas

- The success criteria require a $0.01 budget test that halts after the first real API call -- record_usage() must be called with actual response.usage data
- Retry messages should feel consistent with the "clean output like uv/ruff" preference from Phase 1 -- informative but not noisy
- All four requirements (CORE-08, RES-01, OBS-02, HARV-08) are about wiring existing code, not building new infrastructure

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TokenBudget` class (budget.py): record_usage(), exceeded property, sync_to_state() -- fully implemented, never called from production
- `api_retry` decorator (resilience.py): tenacity-based with exponential backoff + jitter, handles Anthropic exceptions only
- `traceable_agent` decorator (tracing.py): LangSmith @traceable wrapper with phase/agent_name/iteration metadata -- never applied to agents
- `detect_version` function (harvest/version_check.py): semver detection, called in HarvestAgent but detected_version set via model_copy
- `check_version_conflicts` function (harvest/version_check.py): cross-page version comparison, returns conflicts and warnings

### Established Patterns
- Conductor dispatches agents via `_PHASE_AGENT_MAP` dict and checks `budget.exceeded` after each call (conductor.py:165)
- `_build_kwargs(phase, state)` centralizes focused kwargs dispatch in conductor
- `asyncio.to_thread()` bridge for sync-to-async (Phase 2 convention)
- System prompts as module-level `_SYSTEM_PROMPT` constants (Phase 2 convention)
- Test-friendly retry timings (initial=0.01s) to keep test suite fast (Phase 1 decision)
- `_is_retryable()` only classifies Anthropic exceptions (RateLimitError, APIConnectionError, 5xx APIStatusError)

### Integration Points
- Conductor agent dispatch loop (conductor.py) -- where budget.record_usage() should be wired
- All agent `.run()` methods -- where @traceable_agent and @api_retry should be applied
- Firecrawl/Exa/Tavily SDK calls in harvest agents -- where non-Anthropic retry needs to cover
- HarvestAgent post-processing (harvest.py:167-169) -- where detected_version is set via model_copy
- CLI warning/logger output -- where retry messages need to surface in normal mode

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-integration-wiring*
*Context gathered: 2026-03-05*
