# Phase 4: Integration Wiring - Research

**Researched:** 2026-03-05
**Domain:** Integration wiring -- connecting existing tested infrastructure to production code paths
**Confidence:** HIGH

## Summary

Phase 4 is a pure wiring phase: all infrastructure components (TokenBudget, api_retry, traceable_agent, detect_version) already exist and are tested in isolation. The work is connecting them to the correct call sites in production code. There are four distinct integration areas: (1) budget recording in the conductor after each agent's Anthropic API call, (2) retry coverage extended from Anthropic-only to all external SDKs (Firecrawl, Exa, Tavily), (3) LangSmith tracing decoration on agent run methods, and (4) fixing the version detection bug in HarvestAgent where `model_copy()` creates a new object but the original page in the list is never replaced.

**Primary recommendation:** Wire each concern at the narrowest integration point -- budget recording where `response.usage` is accessible (inside each agent after `messages.parse`), retry wrappers at the SDK call sites (strategy functions), tracing at agent `run()` methods, and the version fix via in-place list update in HarvestAgent._harvest.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-08 | Global token budget cap prevents runaway costs in feedback loops | Budget recording pattern, response.usage access, conductor halt flow |
| RES-01 | Exponential backoff on all external API calls (Anthropic, Exa, Tavily, Firecrawl) | SDK exception mapping, unified retry decorator with per-SDK retryable classification |
| OBS-02 | Each agent run includes metadata tags for phase, agent name, and iteration number | traceable_agent decorator application pattern, conductor dispatch integration |
| HARV-08 | Version numbers are detected across sources and conflicts are flagged | model_copy bug fix in HarvestAgent, list mutation pattern |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| tenacity | >=9.1,<10 | Retry decorator with exponential backoff + jitter | Already in pyproject.toml |
| langsmith | >=0.7,<1 | LangSmith @traceable decorator and Anthropic client wrapping | Already in pyproject.toml |
| anthropic | >=0.84,<1 | API calls with response.usage for budget tracking | Already in pyproject.toml |
| firecrawl-py | >=4.18,<5 | Docs site crawling | Already in pyproject.toml |
| exa-py | >=2.7,<3 | Semantic search | Already in pyproject.toml |
| tavily-python | >=0.7,<1 | Web search | Already in pyproject.toml |
| rich | >=14.0,<15 | CLI output for retry messages | Already in pyproject.toml |

### No New Dependencies
This phase adds zero new packages. All wiring uses existing infrastructure.

## Architecture Patterns

### Pattern 1: Budget Recording -- Distributed in Agents, Returning Usage
**What:** Each agent that makes Anthropic API calls extracts `response.usage` and returns usage alongside its result. The conductor calls `budget.record_usage()` after each agent completes.
**Why distributed in agents:** The `response` object (with `.usage.input_tokens` and `.usage.output_tokens`) is only available inside the agent where `client.messages.parse()` is called. The conductor never sees the raw API response.
**Why not fully inside agents:** Agents don't have access to the `TokenBudget` object (by design -- agents receive focused kwargs, not pipeline infrastructure). The conductor owns the budget.

**Recommended approach:** Agents return usage metadata alongside their normal result. The conductor extracts and records it.

```python
# Inside each agent's run() method, after messages.parse():
response = self.client.messages.parse(...)
result = response.parsed_output

# Return usage metadata alongside result
# Store on the result object or return as a tuple
# Approach: attach _usage_meta to the result
result._usage_meta = {  # type: ignore[attr-defined]
    "model": response.model,
    "input_tokens": response.usage.input_tokens,
    "output_tokens": response.usage.output_tokens,
}
return result
```

```python
# In conductor._run_phase(), after agent.run() returns:
result = agent.run(**kwargs)

# Extract usage metadata if present
usage_meta = getattr(result, "_usage_meta", None)
if usage_meta:
    self.budget.record_usage(
        usage_meta["model"],
        input_tokens=usage_meta["input_tokens"],
        output_tokens=usage_meta["output_tokens"],
    )
```

**Confidence:** HIGH -- verified that `ParsedMessage` inherits from `Message` and has `.usage` with `.input_tokens: int` and `.output_tokens: int`, plus `.model: str`.

**Key detail -- multi-call agents:** Some agents make multiple API calls:
- HarvestAgent: `generate_search_queries` (1 call) + `check_saturation` (1 call) = 2 Anthropic calls
- ValidatorAgent: up to 3 parallel LLM evaluator calls (api_accuracy, completeness, trigger_quality)
- Other agents: exactly 1 `messages.parse` call each

For multi-call agents, usage should be accumulated and total returned.

### Pattern 2: Unified Retry with Per-SDK Retryable Classification
**What:** Extend the existing `_is_retryable()` function and `api_retry` decorator to handle all three external SDKs in addition to Anthropic.

**SDK Exception Analysis (verified from installed SDK source):**

| SDK | Retryable Exceptions | Non-Retryable Exceptions |
|-----|---------------------|--------------------------|
| **Anthropic** | `RateLimitError` (429), `APIConnectionError`, `APIStatusError` (5xx) | `AuthenticationError` (401), `BadRequestError` (400), `NotFoundError` (404) |
| **Firecrawl** | `RateLimitError` (429), `InternalServerError` (500), `RequestTimeoutError` (408) | `UnauthorizedError` (401), `BadRequestError` (400), `PaymentRequiredError` (402), `WebsiteNotSupportedError` (403) |
| **Exa** | `ValueError` with status >= 500 or network errors, `requests.ConnectionError`, `requests.Timeout` | `ValueError` with status 400/401/404 |
| **Tavily** | `UsageLimitExceededError` (429), `requests.ConnectionError`, `requests.Timeout`, `response.raise_for_status()` for 5xx | `InvalidAPIKeyError` (401), `BadRequestError` (400), `ForbiddenError` (403) |

**Recommended approach:** Create an `_is_retryable_any()` function that classifies exceptions from ALL SDKs:

```python
import requests
from firecrawl.v2.utils.error_handler import (
    FirecrawlError,
    RateLimitError as FirecrawlRateLimitError,
    InternalServerError as FirecrawlInternalServerError,
    RequestTimeoutError as FirecrawlRequestTimeoutError,
)
from tavily.errors import UsageLimitExceededError as TavilyRateLimitError


def _is_retryable_any(exc: BaseException) -> bool:
    """Determine whether an exception from ANY external SDK is retryable."""
    # Anthropic (existing logic)
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500

    # Firecrawl
    if isinstance(exc, (FirecrawlRateLimitError, FirecrawlInternalServerError, FirecrawlRequestTimeoutError)):
        return True
    if isinstance(exc, FirecrawlError) and exc.status_code and exc.status_code >= 500:
        return True

    # Tavily
    if isinstance(exc, TavilyRateLimitError):
        return True

    # Exa (raises ValueError with status code in message)
    # Also catch generic network errors from requests (used by Exa and Tavily)
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True

    # httpx errors (used by Firecrawl async and GitHub strategy)
    try:
        import httpx
        if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
            return True
    except ImportError:
        pass

    return False
```

**Confidence:** HIGH -- verified all exception classes from installed SDK source code.

**Retry visibility (locked decision):** The existing `before_sleep` callback in `api_retry` uses `logger.warning()`. To meet the locked decision that retries appear in normal CLI output (not just --verbose), change the callback to also print:

```python
def _retry_callback(retry_state):
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    exc_name = type(exc).__name__ if exc else "unknown"
    # Determine the service from the exception type
    service = _identify_service(exc)
    msg = f"  Retrying {service} (attempt {retry_state.attempt_number + 1})..."
    logger.warning(msg)
    print(msg)  # User-visible per locked decision
```

### Pattern 3: Tracing Decoration at Agent Run Methods
**What:** Apply `@traceable_agent` to each agent's `run()` method so every agent call creates a LangSmith span with phase, agent_name, and iteration metadata.

**Challenge:** The decorator is currently a static decorator factory -- it takes `phase`, `agent_name`, and `iteration` as arguments at decoration time. But `iteration` is dynamic (varies per call in feedback loops).

**Recommended approach:** Apply the decorator dynamically in the conductor's dispatch, not statically on the class:

```python
# In conductor._run_phase():
from skill_builder.tracing import traceable_agent

phase_label = phase.value
agent_key = self._PHASE_AGENT_MAP.get(phase)
iteration = state.gap_loop_count if "harvest" in agent_key else state.validation_loop_count

# Wrap the run method with tracing for this specific call
traced_run = traceable_agent(
    name=f"{agent_key}_run",
    phase=phase_label,
    agent_name=agent_key,
    iteration=iteration,
)(agent.run)

result = traced_run(**kwargs)
```

This ensures each call gets the correct iteration count without modifying agent classes.

**Confidence:** HIGH -- verified `traceable_agent` returns a decorator that wraps any callable, and the existing no-op fallback ensures this is safe when LangSmith is unavailable.

### Pattern 4: Version Detection Bug Fix
**What:** In `HarvestAgent._harvest()` lines 166-169, `model_copy()` creates a new `HarvestPage` with `detected_version` set, but the new object is assigned to the loop variable `page` -- not put back into the `pages` list. The original objects in `pages` still have `detected_version=None`.

```python
# CURRENT (buggy):
for page in pages:
    versions = detect_version(page.content)
    if versions:
        page = page.model_copy(update={"detected_version": versions[0]})
        # ^^^ This creates a new object, but pages[i] still points to the old one

# FIX:
for i, page in enumerate(pages):
    versions = detect_version(page.content)
    if versions:
        pages[i] = page.model_copy(update={"detected_version": versions[0]})
```

**Confidence:** HIGH -- this is a straightforward Python loop variable rebinding bug. The `model_copy()` call returns a new Pydantic model instance; reassigning `page` does not mutate the list.

### Recommended Project Structure Changes
```
src/skill_builder/
    resilience.py           # Extended: _is_retryable_any(), api_retry updated
    conductor.py            # Modified: budget recording, tracing wiring
    agents/
        harvest.py          # Modified: version fix, usage metadata
        organizer.py        # Modified: usage metadata
        gap_analyzer.py     # Modified: usage metadata
        learner.py          # Modified: usage metadata
        mapper.py           # Modified: usage metadata
        documenter.py       # Modified: usage metadata
        validator.py        # Modified: usage metadata (multi-call)
    harvest/
        firecrawl_strategy.py  # Modified: @api_retry wrapper
        exa_strategy.py        # Modified: @api_retry wrapper
        tavily_strategy.py     # Modified: @api_retry wrapper
        github_strategy.py     # Modified: @api_retry wrapper (httpx calls)
        query_generator.py     # Modified: @api_retry on LLM calls
        saturation.py          # Modified: usage metadata
    evaluators/
        api_accuracy.py        # Modified: @api_retry on LLM call, usage metadata
        completeness.py        # Modified: @api_retry on LLM call, usage metadata
        trigger_quality.py     # Modified: @api_retry on LLM call, usage metadata
```

### Anti-Patterns to Avoid
- **Passing TokenBudget into agents:** Agents should not know about budget. The conductor owns this concern.
- **Static @traceable_agent on class definitions:** Iteration number is dynamic; decorate at call time in the conductor.
- **Wrapping entire agent.run() in api_retry:** The retry should be at the API call site (the specific `messages.parse()` or SDK call), not the entire agent orchestration. An agent may do non-idempotent work before the API call.
- **Catching all Exceptions as retryable:** Only specific transient error types should trigger retry. Auth errors, bad requests, etc. should fail immediately.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom sleep loops | tenacity `api_retry` decorator | Handles jitter, max attempts, selective retry, logging out of the box |
| LangSmith tracing | Manual span creation | `traceable_agent` decorator | Handles LangSmith unavailability gracefully (RES-02) |
| Token cost calculation | Manual pricing lookups | `TokenBudget.record_usage()` | Already handles per-model pricing and accumulation |
| Version detection | Custom regex per agent | `detect_version()` from version_check.py | Already tested, handles semver patterns |

## Common Pitfalls

### Pitfall 1: model_copy Loop Variable Rebinding
**What goes wrong:** `page = page.model_copy(update={...})` in a `for page in pages` loop creates a new object but never updates the list. The original list items remain unchanged.
**Why it happens:** Pydantic models are immutable-by-default; `model_copy()` returns a new instance. Python loop variable reassignment does not mutate the iterable.
**How to avoid:** Use `enumerate` and assign back: `pages[i] = page.model_copy(...)`.
**Warning signs:** `detected_version` is always None in HarvestResult pages despite content containing version strings.

### Pitfall 2: Retry on Non-Idempotent Operations
**What goes wrong:** Retrying an entire agent.run() that has already written partial state or made irreversible calls.
**Why it happens:** Wrapping too much code in the retry scope.
**How to avoid:** Place retry decorators only on the specific API call function, not the orchestration logic.
**Warning signs:** Duplicate data, repeated side effects after transient failures.

### Pitfall 3: Exa SDK Exception Opacity
**What goes wrong:** Exa raises plain `ValueError` for all HTTP errors (including 500s). The status code is embedded in the error message string, not in a structured attribute.
**Why it happens:** The Exa SDK has minimal exception hierarchy -- just `ValueError` for all failures.
**How to avoid:** For Exa, consider catching `ValueError` generically as retryable (since authentication/key errors prevent even reaching the API call in the wrapped `asyncio.to_thread` context), OR parse the message for status codes. The simpler approach: catch `ValueError` and `requests.exceptions.*` from Exa calls, since the most common transient failures are `ConnectionError` and `Timeout` which are already handled.
**Warning signs:** Exa retries on 401/400 errors unnecessarily.

### Pitfall 4: Retry Timings Breaking Tests
**What goes wrong:** Production-realistic retry timings (1s initial, 60s max) make tests wait minutes.
**Why it happens:** The same decorator is used in both production and test paths.
**How to avoid:** Keep the existing test-friendly defaults (initial=0.01s, max=0.1s) as the decorator defaults. Use environment-based or parameter-based override for production timings if needed. Per Phase 1 decision: test-friendly timings by default.
**Warning signs:** Test suite runtime jumps from seconds to minutes.

### Pitfall 5: Budget Recording with Thinking Tokens
**What goes wrong:** Anthropic responses with `thinking` enabled may have different token accounting. The `response.usage` still reports `input_tokens` and `output_tokens` but thinking tokens are part of output_tokens.
**Why it happens:** GapAnalyzerAgent uses `thinking={"type": "adaptive"}`.
**How to avoid:** Use `response.usage.input_tokens` and `response.usage.output_tokens` as-is -- they already include thinking costs. The per-model pricing in TokenBudget handles this correctly since thinking tokens are billed at the same output rate.
**Warning signs:** None -- this is a non-issue if using the usage fields directly.

### Pitfall 6: Async Strategy Functions and Retry
**What goes wrong:** `api_retry` uses tenacity's synchronous retry mechanism, but `exa_search`, `tavily_search`, and `firecrawl_crawl` are async functions.
**Why it happens:** The sync `@retry` decorator doesn't work with async functions.
**How to avoid:** For the async strategy functions, the actual SDK calls happen inside `asyncio.to_thread()` (Exa, Tavily) or are natively async (Firecrawl). Options:
1. Use tenacity's async support: `from tenacity import AsyncRetrying` for async functions
2. Wrap the inner sync SDK call with the sync retry decorator before passing to `asyncio.to_thread()`
3. Create a simple async retry wrapper

The cleanest approach: wrap the inner sync SDK call (for Exa/Tavily) with the sync decorator, and use tenacity's async retry for the Firecrawl async call.

## Code Examples

### Budget Recording in an Agent (Verified Pattern)
```python
# Source: Verified from anthropic SDK -- ParsedMessage inherits Message with .usage
# In OrganizerAgent.run():
response = self.client.messages.parse(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    output_format=CategorizedResearch,
    system=_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": prompt}],
)

result: CategorizedResearch = response.parsed_output

# Attach usage metadata for conductor to extract
result._usage_meta = {  # type: ignore[attr-defined]
    "model": response.model,
    "input_tokens": response.usage.input_tokens,
    "output_tokens": response.usage.output_tokens,
}
return result
```

### Conductor Budget Recording (Verified Pattern)
```python
# Source: Existing conductor._run_phase pattern
# After agent.run() returns:
result = agent.run(**kwargs)

# Record usage if agent provides it
usage_meta = getattr(result, "_usage_meta", None)
if usage_meta:
    self.budget.record_usage(
        usage_meta["model"],
        input_tokens=usage_meta["input_tokens"],
        output_tokens=usage_meta["output_tokens"],
    )
```

### Extended Retry for Non-Anthropic SDKs
```python
# Source: Verified from installed SDK source code
# In resilience.py -- extend _is_retryable to _is_retryable_any

import requests
from firecrawl.v2.utils.error_handler import (
    FirecrawlError,
    RateLimitError as FirecrawlRateLimitError,
    InternalServerError as FirecrawlInternalServerError,
    RequestTimeoutError as FirecrawlRequestTimeoutError,
)
from tavily.errors import UsageLimitExceededError as TavilyUsageLimitError

def _is_retryable_any(exc: BaseException) -> bool:
    """Classify transient errors from all external SDKs."""
    # Anthropic
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return True
    # Firecrawl
    if isinstance(exc, (FirecrawlRateLimitError, FirecrawlInternalServerError, FirecrawlRequestTimeoutError)):
        return True
    # Tavily
    if isinstance(exc, TavilyUsageLimitError):
        return True
    # Generic network errors (requests -- used by Exa and Tavily)
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    # httpx errors (Firecrawl async, GitHub strategy)
    if isinstance(exc, Exception):
        try:
            import httpx
            if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
                return True
        except ImportError:
            pass
    return False
```

### Retry Visible in Normal CLI (Locked Decision)
```python
# In resilience.py -- retry callback with user-visible output
def _make_before_sleep_callback():
    """Create a before_sleep callback that prints retry messages to CLI."""
    def callback(retry_state):
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        exc_name = type(exc).__name__ if exc else "unknown"
        attempt = retry_state.attempt_number + 1
        # Use print() for user visibility (per locked decision: not just --verbose)
        msg = f"  Retrying after {exc_name} (attempt {attempt})..."
        logger.warning(msg)
        print(msg)
    return callback
```

### Version Detection Fix
```python
# In HarvestAgent._harvest(), step 6:
# FIX: Use enumerate to update the list in-place
for i, page in enumerate(pages):
    versions = detect_version(page.content)
    if versions:
        pages[i] = page.model_copy(update={"detected_version": versions[0]})
```

### Dynamic Tracing in Conductor
```python
# In conductor._run_phase():
from skill_builder.tracing import traceable_agent

# Determine iteration for tracing metadata
if phase in (PipelinePhase.RE_HARVESTING, PipelinePhase.GAP_ANALYZING):
    iteration = state.gap_loop_count
elif phase in (PipelinePhase.RE_PRODUCING, PipelinePhase.VALIDATING):
    iteration = state.validation_loop_count
else:
    iteration = 0

# Wrap agent.run with tracing
traced_run = traceable_agent(
    name=f"{agent_key}_run",
    phase=phase_label,
    agent_name=agent_key,
    iteration=iteration,
)(agent.run)

result = traced_run(**kwargs)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Anthropic-only retry in `_is_retryable()` | Unified retry for all SDKs via `_is_retryable_any()` | Phase 4 | All external API calls get exponential backoff |
| Budget infrastructure exists but unused | Budget recording wired via `_usage_meta` on agent results | Phase 4 | Runaway costs prevented by budget cap |
| `traceable_agent` defined but never applied | Dynamic decoration in conductor dispatch | Phase 4 | LangSmith spans with full metadata per agent call |
| Version detection called but results discarded (loop var bug) | Fixed with enumerate + list update | Phase 4 | `detected_version` populated in HarvestResult.pages |

## Open Questions

1. **Exa ValueError retryability**
   - What we know: Exa raises `ValueError` for ALL HTTP errors, with status code embedded in message string. No structured `status_code` attribute.
   - What's unclear: Whether to catch `ValueError` broadly (risks retrying on actual bad requests) or parse the message for status codes.
   - Recommendation: Catch `requests.ConnectionError` and `requests.Timeout` from Exa (these are the common transient failures). Don't catch `ValueError` generically -- let it propagate as a permanent failure. Exa 500 errors are rare; connection/timeout issues are the realistic transient failures.

2. **Multi-call agent usage accumulation**
   - What we know: HarvestAgent makes 2 Anthropic calls (query generation + saturation check). ValidatorAgent makes 3 parallel LLM evaluator calls.
   - What's unclear: Whether to accumulate usage inside the agent or return multiple usage entries.
   - Recommendation: Accumulate within the agent and return a single total. The conductor doesn't need per-call granularity -- LangSmith provides that level of detail.

3. **Retry timing for production vs test**
   - What we know: Current defaults are test-friendly (initial=0.01s, max=0.1s). Production-realistic would be (initial=1s, max=60s).
   - What's unclear: Whether the fast defaults are acceptable for production (this is a local Mac CLI tool, not a high-availability service).
   - Recommendation: Keep test-friendly defaults in the decorator. For production, the fast retry is actually fine -- the jitter prevents thundering herd, and a local CLI tool doesn't need long backoff. The current 0.01s initial is perhaps too aggressive for production; a compromise of 0.5s initial, 10s max would work. This can be parameterized.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 with pytest-asyncio >= 0.25 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/python -m pytest tests/ -x --timeout=10` |
| Full suite command | `.venv/bin/python -m pytest tests/ -v --timeout=10` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-08 | Budget recording called with actual response.usage data; conductor halts when budget.exceeded | unit | `.venv/bin/python -m pytest tests/test_conductor.py::TestBudgetRecording -x` | No -- Wave 0 |
| CORE-08 | Budget halt message displayed via progress or print | unit | `.venv/bin/python -m pytest tests/test_conductor.py::TestBudgetExceeded -x` | Partial -- existing tests check halt, not recording |
| RES-01 | Firecrawl/Exa/Tavily transient errors trigger retries | unit | `.venv/bin/python -m pytest tests/test_resilience.py::TestUnifiedRetry -x` | No -- Wave 0 |
| RES-01 | Retry messages visible in normal output | unit | `.venv/bin/python -m pytest tests/test_resilience.py::TestRetryVisibility -x` | No -- Wave 0 |
| OBS-02 | Agent.run() calls create LangSmith spans with correct metadata | unit | `.venv/bin/python -m pytest tests/test_tracing.py::TestTracingIntegration -x` | No -- Wave 0 |
| HARV-08 | HarvestPage.detected_version populated after harvest | unit | `.venv/bin/python -m pytest tests/test_harvest_agent.py::TestVersionPersistence -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/ -x --timeout=10`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -v --timeout=10`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_resilience.py` -- add TestUnifiedRetry class for non-Anthropic SDK exceptions
- [ ] `tests/test_resilience.py` -- add TestRetryVisibility class for CLI output
- [ ] `tests/test_conductor.py` -- add TestBudgetRecording class for usage metadata extraction
- [ ] `tests/test_harvest_agent.py` -- add TestVersionPersistence class for detected_version fix
- [ ] `tests/test_tracing.py` -- add TestTracingIntegration class for conductor dispatch tracing

## Sources

### Primary (HIGH confidence)
- Anthropic SDK source code (installed v0.84+) -- `ParsedMessage` inherits `Message`, has `.usage.input_tokens: int`, `.usage.output_tokens: int`, `.model: str`
- Firecrawl SDK source code (installed v4.18+) -- `FirecrawlError` base with `RateLimitError`, `InternalServerError`, `RequestTimeoutError`, `UnauthorizedError`, `BadRequestError`, `PaymentRequiredError`, `WebsiteNotSupportedError`
- Exa SDK source code (installed v2.7+) -- uses `requests`, raises `ValueError` for all HTTP errors with status code in message
- Tavily SDK source code (installed v0.7+) -- `UsageLimitExceededError` (429), `InvalidAPIKeyError` (401), `BadRequestError` (400), `ForbiddenError` (403), `TimeoutError`
- Existing project codebase -- `budget.py`, `resilience.py`, `tracing.py`, `conductor.py`, all agent files

### Secondary (MEDIUM confidence)
- [Firecrawl Python SDK docs](https://docs.firecrawl.dev/sdks/python) -- SDK methods and error handling overview
- [Tavily SDK Reference](https://docs.tavily.com/sdk/python/reference) -- exception classes documentation
- [Exa Python SDK Specification](https://docs.exa.ai/sdks/python-sdk-specification) -- API reference

### Tertiary (LOW confidence)
- None -- all findings verified from installed source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all verified from pyproject.toml
- Architecture: HIGH -- all patterns verified against existing codebase and SDK source
- Pitfalls: HIGH -- all verified from actual code inspection (especially the model_copy bug)
- SDK exceptions: HIGH -- all verified from installed source code, not documentation

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- no fast-moving dependencies)
