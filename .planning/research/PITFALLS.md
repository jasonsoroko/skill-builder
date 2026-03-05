# Domain Pitfalls

**Domain:** Multi-agent LLM pipeline for skill file generation (Python CLI)
**Researched:** 2026-03-05

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or cost blowouts.

---

### Pitfall 1: Feedback Loop Runaway (Cost and Token Explosion)

**What goes wrong:** The Gap Analyzer finds gaps, sends the pipeline back to harvest, which feeds new content to the Organizer, which feeds back to the Gap Analyzer -- which finds *new* gaps from the new content. Each loop iteration compounds: more content means larger context windows, higher token costs per call, and potentially new gaps that were not present before. An uncapped loop on Opus 4.6 with extended thinking can burn through hundreds of dollars in minutes.

**Why it happens:** The gap detection threshold is never truly "zero gaps" because LLMs can always find something to improve. Without hard limits, the system optimizes indefinitely. The project spec calls for "loop back to harvest when gaps are found" with no explicit cap.

**Consequences:** $50-200+ per run instead of $2-5. Context windows overflow. Run times stretch from minutes to hours. LangSmith traces become unreadable.

**Prevention:**
- Hard cap: maximum 2 feedback loops (harvest -> synthesis -> gap check -> harvest -> synthesis -> gap check -> proceed). The third iteration always proceeds.
- Token budget per run: set a global budget (e.g., 500K input tokens total across all agents). The conductor tracks cumulative usage and forces termination when budget is 80% consumed.
- Gap severity threshold: only loop back for gaps scored "critical" by the Gap Analyzer -- missing required_capabilities, not "could be more detailed."
- Shrinking context: on each loop iteration, pass only the *delta* (new search queries + new content), not the full accumulated corpus.

**Detection:** LangSmith total token count per run exceeding 200K input tokens. More than 2 gap-analysis phases in a single run. Run duration exceeding 10 minutes.

**Phase:** Implement in Phase 1 (conductor state machine). This is the single most important guardrail in the system.

---

### Pitfall 2: Anthropic tool_use stop_reason Mishandling

**What goes wrong:** Your code sends a tool_use request to Claude, but the response comes back with `stop_reason: "end_turn"` instead of `stop_reason: "tool_use"`. The code does not check for this and tries to parse `response.content[0].input` (the tool_use block), but finds a text block instead. Result: `KeyError` or `AttributeError` crash. Alternatively, the model returns *both* a text block and a tool_use block in the same response, and your code only reads the first content block.

**Why it happens:** Claude can decide not to use the tool even when you request it (unless `tool_choice: "any"` forces it). Extended thinking adds thinking blocks before tool_use blocks, changing the index of content blocks. The response is a *list* of content blocks -- text, thinking, and tool_use can all coexist.

**Consequences:** Silent data loss (text response discarded), crashes on missing tool_use blocks, or extraction of wrong content block.

**Prevention:**
- Always iterate `response.content` and filter by `block.type == "tool_use"` rather than indexing `response.content[0]`.
- Use `tool_choice: {"type": "any"}` for all agent calls where you *require* structured output (Organizer, Learner, Mapper, Documenter, Gap Analyzer). This forces tool use.
- Validate that exactly one tool_use block is returned; if zero, retry with a clearer prompt. If multiple, take the first matching your expected tool name.
- When using extended thinking with tool_use: `tool_choice` only supports `any` -- not `auto`, not a specific tool name. This is a hard constraint from the API.

**Detection:** Any agent call that returns no Pydantic model. Log the raw `stop_reason` on every API call.

**Phase:** Phase 1 (agent wrapper layer). Must be correct before any agent is built.

---

### Pitfall 3: Extended Thinking + Tool Use Interaction Bugs

**What goes wrong:** You enable adaptive/extended thinking on Opus for the Gap Analyzer and LLM-as-judge evaluators. The thinking blocks must be passed back in subsequent messages. If you strip them, modify them, or forget to include them in the conversation history, Claude loses reasoning context. Additionally, `budget_tokens` must be strictly less than `max_tokens`, and changes to the thinking budget invalidate cached prompt prefixes (but not cached system prompts or tool definitions).

**Why it happens:** The interleaved thinking feature (thinking between tool calls) requires the beta header `interleaved-thinking-2025-05-14` for Claude 4 models. Without it, thinking only happens once before the first tool call. The thinking blocks are opaque and large, which tempts developers to strip them to save context space.

**Consequences:** Degraded reasoning quality on evaluation calls. Cache misses increasing cost. Subtle: the Gap Analyzer starts missing real gaps or the LLM-as-judge gives inflated scores because it lost its chain of thought.

**Prevention:**
- Always pass thinking blocks back unmodified in the `messages` array. Never filter, truncate, or summarize them.
- Set `budget_tokens` to start at 1,024 and increase only if evaluation quality is poor. For Gap Analyzer and judges, 4,096 is a reasonable ceiling.
- Include the interleaved thinking beta header for Claude 4 models.
- Keep system prompts and tool definitions stable across calls to maximize cache hits. Only message content busts the cache when budget changes.

**Detection:** Declining evaluation scores over time without prompt changes. Unexpected cache miss rates in LangSmith cost tracking.

**Phase:** Phase 2 (Gap Analyzer and evaluator implementation). Test with and without extended thinking to verify quality difference justifies cost.

---

### Pitfall 4: State Machine Missing Terminal States

**What goes wrong:** The deterministic conductor state machine has paths that never reach a terminal state. Example: evaluator scores below 7, routes back to production agents, which produce output that again scores below 7 -- infinite production/evaluation loop. Or: harvest finds zero results for a URL, but there is no "skip and continue" transition, so the machine hangs.

**Why it happens:** State machines are designed for the happy path first. Error states, empty-result states, and "good enough after N retries" states are added as afterthoughts -- or not at all. Research on multi-agent system failures (MAST taxonomy, Cemri et al. 2025) found that task verification and termination failures are one of three major failure categories, alongside specification failures and inter-agent misalignment.

**Consequences:** Pipeline hangs indefinitely. Or worse: pipeline completes with corrupt state because an error state fell through to the next phase without proper data.

**Prevention:**
- Every state must have an explicit error transition and a "max retries exceeded" transition that leads to a degraded-but-terminal state.
- Evaluator loop: max 2 production retries. After that, emit the best-scoring version with a warning flag rather than looping forever.
- Harvest empty-result: if a URL returns nothing after retries, log it and continue to the next URL. If *all* URLs return nothing, transition to a "harvest failed" terminal state.
- Draw the state machine diagram and verify every state has at least two outgoing transitions (success + failure). Use a formal check: `assert all(len(state.transitions) >= 2 for state in machine.states if not state.is_terminal)`.

**Detection:** Any run that exceeds 15 minutes. Any state visited more than 3 times in a single run.

**Phase:** Phase 1 (conductor design). The state machine is the backbone -- get it right before building agents.

---

### Pitfall 5: LangSmith @traceable Crashing the Pipeline

**What goes wrong:** The `@traceable` decorator encounters a network error, 403, or 500 from the LangSmith API, and this error propagates up and crashes your application. Tracing -- which should be observability-only -- becomes a point of failure.

**Why it happens:** By default, LangSmith SDK errors in the `@traceable` decorator can bubble up to application code. This was a known issue (langsmith-sdk issue #1306). The SDK has improved, but misconfiguration or network issues can still cause problems. Additionally, if `LANGCHAIN_TRACING_V2` is not set or `LANGCHAIN_API_KEY` is missing, the decorator may behave unexpectedly (silently no-op or raise).

**Consequences:** A perfectly valid skill-building run fails because LangSmith was temporarily unreachable. Pipeline reliability is coupled to an external observability service.

**Prevention:**
- Wrap all LangSmith interactions with try/except at the integration boundary. Do not let tracing errors propagate.
- Set `LANGCHAIN_TRACING_V2=true` explicitly in your CLI startup. Validate env vars on startup and warn (but don't crash) if missing.
- Test the pipeline with LangSmith intentionally disabled (`LANGCHAIN_TRACING_V2=false`) to verify it runs independently.
- Use the `tracing_enabled` context manager for explicit scope control rather than relying solely on environment variables.

**Detection:** Any unhandled exception from `langsmith` or `langchain_core` packages in production logs.

**Phase:** Phase 1 (infrastructure layer). Implement the tracing wrapper once and use it everywhere.

---

### Pitfall 6: Content Deduplication Failures Causing Contradictory Knowledge

**What goes wrong:** The same documentation appears at multiple URLs (e.g., `/docs/v2/api` and `/api/reference` and the GitHub README all describe the same API). The pipeline treats each as unique source content. When the Organizer synthesizes, it finds three descriptions of the same feature with slight wording differences, leading to redundant or contradictory entries in the KnowledgeModel. The final skill file ends up with duplicate sections or, worse, conflicting version information.

**Why it happens:** URL-based deduplication is insufficient -- the same content lives at many URLs. Simple content hashing fails when pages have different navbars, footers, or timestamps. Version-specific docs (v1 vs v2) may have 90% overlap but critical 10% differences that need to be preserved, not deduped.

**Consequences:** Skill files exceed 500 lines due to redundancy. Contradictory API information (v1 and v2 mixed). The LLM-as-judge evaluator catches some of this but wastes expensive Opus calls on content that should have been deduped earlier.

**Prevention:**
- Two-level dedup: (1) URL normalization (strip query params, fragments, trailing slashes, canonicalize paths) (2) content hash on the *extracted markdown body only* (strip navigation, headers, footers before hashing).
- For near-duplicate detection: use a simple similarity threshold (e.g., if two documents share >80% of their content by simhash or minhash, flag for manual merge).
- Version awareness: extract version numbers from URLs and content. Store version as metadata. The Organizer should receive version tags and explicitly resolve conflicts by preferring the latest version.
- Saturation check should consider deduped content count, not raw URL count.

**Detection:** More than 3 sources with >80% content similarity in a single harvest. KnowledgeModel with duplicate capability entries.

**Phase:** Phase 1 (harvest pipeline). Dedup must happen before content enters the synthesis pipeline.

---

## Moderate Pitfalls

---

### Pitfall 7: Firecrawl Credit Burn on JS-Rendered Pages

**What goes wrong:** Every Firecrawl scrape with JavaScript rendering costs 2-3 credits instead of 1. Using `crawl_url` on a large docs site with `max_pages=50` plus JS rendering burns 100-150 credits. The queue timeout counts against your request timeout, so a backed-up queue causes timeout failures *before processing even starts*.

**Prevention:**
- Default to `scrape_url` (single page) rather than `crawl_url` (full site crawl). Only crawl when you explicitly need to discover linked pages.
- Request markdown format only -- skip HTML, screenshots, and other formats to reduce credit cost.
- Use Firecrawl's batch scraping endpoint for multiple URLs rather than concurrent individual requests (it handles rate limiting internally).
- Set explicit timeout higher than default (60s+) to account for queue wait time.
- Track credit usage per run and set a per-run credit ceiling.

**Detection:** Credit usage per run exceeding 200. Timeout errors from Firecrawl before content is returned.

**Phase:** Phase 1 (harvest layer). Configure Firecrawl client once with conservative defaults.

---

### Pitfall 8: Exa/Tavily API Cost Complexity and Result Quality Variance

**What goes wrong:** Exa's pricing varies by endpoint, search type (Neural vs Keyword), number of results, and whether full content is retrieved. A "simple" search that retrieves full content for 10 results costs significantly more than a search that returns only URLs. Tavily charges 1 credit for basic search, 2 for advanced. The feedback loop multiplies these costs. Result quality also varies: Exa's neural search excels at semantic queries but may return irrelevant results for specific API documentation lookups.

**Prevention:**
- Exa: use `type="keyword"` for specific API/library searches (cheaper, more precise). Reserve `type="neural"` for broad concept searches. Retrieve content only for the top 3-5 results, not all 10.
- Tavily: use basic search (1 credit) by default. Only use advanced (2 credits) when basic returns poor results.
- Cache all search results by query string. Never re-execute the same query in a feedback loop.
- Set per-source query limits: max 5 Exa queries and 5 Tavily queries per run.

**Detection:** More than 10 total search API calls in a single run. Search queries that are near-duplicates of previous queries in the same run.

**Phase:** Phase 1 (search wrapper layer). Implement caching and limits in the search abstraction.

---

### Pitfall 9: Async/Sync Client Mismatch in Anthropic SDK

**What goes wrong:** The Anthropic SDK provides both `Anthropic` (sync) and `AsyncAnthropic` (async) clients. Mixing them in the same codebase -- or wrapping the sync client in `asyncio.to_thread()` -- creates subtle issues. The async client's `AsyncHttpxClientWrapper` has a known garbage collection bug where `__del__` tries to schedule cleanup on a potentially closed event loop, causing "Event loop is closed" exceptions.

**Why it happens:** The project spec calls for "Phase 1 parallelized" (harvest) but "Phase 2 sequential" (synthesis). This naturally leads to async harvest code calling sync synthesis code, or vice versa. If the conductor is sync but harvest is async, you need `asyncio.run()` boundaries that can conflict.

**Prevention:**
- Pick one: either fully sync or fully async. For this project, **use the sync client everywhere**. Parallelism in Phase 1 (harvest) can use `concurrent.futures.ThreadPoolExecutor` with the sync client -- it is thread-safe for separate client instances.
- If async is chosen: use `AsyncAnthropic` everywhere and manage a single event loop. Never mix sync and async Anthropic clients in the same process.
- Create one client instance per thread (not shared across threads). The httpx connection pool is not designed for cross-thread sharing.
- Avoid `asyncio.to_thread()` wrapping of the sync Anthropic client -- it works but adds complexity for no benefit.

**Detection:** "Event loop is closed" exceptions. Hung API calls. Thread deadlocks during harvest.

**Phase:** Phase 1 (client initialization). Decide sync vs async once and enforce it project-wide.

---

### Pitfall 10: LangSmith @traceable Async Generator and Nested Span Breaks

**What goes wrong:** If any agent uses async generators (e.g., streaming responses), `@traceable` does not correctly correlate run IDs -- child spans appear as separate root traces instead of nested under the parent. Additionally, only functions decorated with `@traceable` appear in the trace hierarchy; undecorated helper functions are invisible, making debugging incomplete.

**Prevention:**
- Avoid async generators with `@traceable`. Since this project uses tool_use (not streaming), this is avoidable -- but ensure no streaming code paths exist.
- Decorate *all* significant functions with `@traceable`, not just the top-level agent calls. Include: search functions, content extraction functions, dedup functions, Pydantic validation functions. The trace tree should mirror the pipeline architecture.
- Use `run_type` parameter to categorize spans: `@traceable(run_type="chain")` for orchestration, `@traceable(run_type="llm")` for Anthropic calls, `@traceable(run_type="tool")` for search/scrape calls.

**Detection:** Orphaned traces in LangSmith (root traces that should be children). Missing spans in the trace tree for functions you expected to see.

**Phase:** Phase 1 (tracing infrastructure). Establish the decoration convention early.

---

### Pitfall 11: Pydantic v2 Schema Gotchas with Anthropic tool_use

**What goes wrong:** Anthropic's tool_use requires JSON Schema definitions for tool inputs. Pydantic v2 generates JSON Schema differently from v1. Specific issues: `Optional[str]` in Pydantic v2 means "required but nullable" (not "has default None" like v1). `model_validator` and `field_validator` have different signatures than the v1 `@validator` and `@root_validator`. If your Pydantic models use v1 patterns, the generated JSON schemas will be wrong, and Claude will produce inputs that fail validation.

**Prevention:**
- Use Pydantic v2 from the start (this is greenfield -- no migration needed). But be vigilant about:
  - `Optional[str]` makes the field required. Use `str | None = None` for truly optional fields with a default.
  - Use `model_json_schema()` (not `schema()`) to generate the JSON schema for tool definitions.
  - Test every Pydantic model's generated JSON schema against the Anthropic API *before* building agents. A schema that Pydantic generates may not be exactly what Claude needs.
- Use `strict: true` in tool definitions to get guaranteed schema compliance from Claude's output.
- Avoid `each_item` validators (removed in v2). Use `Annotated[list[str], AfterValidator(...)]` instead.

**Detection:** `ValidationError` from Pydantic when parsing Claude's tool_use output. Fields that should be optional appearing as required in the JSON schema.

**Phase:** Phase 1 (Pydantic model definitions). Define all models and test schema generation before building agents.

---

### Pitfall 12: LLM Output Validation -- Hallucinated APIs in Structured Output

**What goes wrong:** Claude generates a perfectly valid Pydantic model (all fields present, correct types) but the *content* is hallucinated. Example: the skill file references `exa.search_and_contents()` when the actual method is `exa.search()` with a `contents` parameter, or it cites API parameters that existed in v1 but were removed in v2 (like Exa's deprecated `use_autoprompt`).

**Why it happens:** Structured output guarantees format, not factual accuracy. Anthropic's own documentation states: "models can and may still hallucinate occasionally, so you might get perfectly formatted incorrect answers." The model's training data is stale -- Exa recently removed the `highlights` feature and deprecated `use_autoprompt`, but Claude's training data may predate these changes.

**Consequences:** The entire purpose of skill-builder is to produce skills "accurate enough to install without manual editing." A hallucinated API renders the skill harmful -- it will cause Claude Code to generate broken code every time it consults the skill.

**Prevention:**
- The LLM-as-judge evaluator must specifically check API accuracy against the *harvested source content*, not against the model's general knowledge. Provide the judge with the raw harvested documentation as grounding context.
- Heuristic validators should: parse code blocks with `ast.parse()`, extract function/method calls, and cross-reference them against the harvested API surface.
- Include version numbers in all API references in the skill file. The evaluator should verify version consistency.
- For the first target skill (Exa + Tavily + Firecrawl), manually verify the output against live API docs before trusting the pipeline.

**Detection:** Evaluator "API accuracy" score below 8. Code blocks that reference methods not found in harvested content.

**Phase:** Phase 2 (evaluator implementation). This is the hardest evaluator to get right and the most important one.

---

## Minor Pitfalls

---

### Pitfall 13: Click CLI Entry Point Configuration Errors

**What goes wrong:** Click CLI setup issues: forgetting `if __name__ == "__main__"` guard, incorrect `pyproject.toml` entry point syntax (`[project.scripts]` vs `[tool.setuptools.entry_points]`), or Click commands that swallow exceptions silently.

**Prevention:**
- Use `[project.scripts]` in `pyproject.toml` (the modern way): `skill-builder = "skill_builder.cli:main"`.
- Use `click.exceptions.ClickException` for user-facing errors, not raw `sys.exit(1)`.
- Test the CLI entry point with `pip install -e .` before building any pipeline logic.

**Detection:** `ModuleNotFoundError` or `ImportError` when running the installed CLI command.

**Phase:** Phase 1 (project scaffolding). Get this right in the first hour.

---

### Pitfall 14: Checkpoint JSON Serialization Edge Cases

**What goes wrong:** The spec calls for "checkpoint persistence to JSON at every phase boundary." Pydantic models with `datetime`, `bytes`, `set`, or custom types fail to serialize with `json.dumps()`. Large harvested content exceeds JSON file size expectations, making checkpoint files unwieldy.

**Prevention:**
- Use Pydantic's `model_dump_json()` for all checkpoint serialization -- it handles datetime, custom types, etc.
- Compress checkpoint content: store content hashes in the checkpoint, not full content bodies. Keep full content in a separate content store keyed by hash.
- Set a maximum checkpoint file size (e.g., 10MB). If exceeded, split into checkpoint metadata + content store.

**Detection:** `TypeError: Object of type X is not JSON serializable`. Checkpoint files exceeding 10MB.

**Phase:** Phase 1 (checkpoint infrastructure).

---

### Pitfall 15: Dry-Run Mode That Doesn't Actually Test Anything

**What goes wrong:** The spec calls for "dry-run mode that prints fetch plan and exits." If dry-run only validates input and prints URLs, it misses the most common failures: invalid API keys, rate limit configuration, Pydantic model schema errors, and state machine transition bugs.

**Prevention:**
- Dry-run should: validate all API keys (make a trivial call to each service), validate all Pydantic model schemas compile correctly, run the state machine with mock data through at least one complete path, and print the cost estimate for the planned run.
- Separate "plan" mode (just show what would happen) from "validate" mode (actually test connections and schemas).

**Detection:** Users running dry-run, getting "OK", then immediately failing on the real run due to auth or config errors.

**Phase:** Phase 1 (CLI implementation).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Conductor / State Machine | Infinite loops in feedback cycles (Pitfall 1, 4) | Hard caps on loop iterations; every state has error transitions; global token budget |
| Harvest (Scraping/Search) | Credit burn (Pitfall 7, 8), dedup failures (Pitfall 6) | Per-source limits, content hashing, Firecrawl conservative defaults |
| Agent Framework | stop_reason mishandling (Pitfall 2), async/sync mismatch (Pitfall 9) | Filter content blocks by type, pick sync everywhere, one client per thread |
| Pydantic Models | v2 Optional semantics (Pitfall 11) | Use `T \| None = None` pattern, test generated schemas against API |
| Extended Thinking | Thinking block handling (Pitfall 3), budget misconfiguration | Pass blocks back unmodified, start budget at 1,024, use interleaved thinking beta header |
| Tracing | LangSmith crash-through (Pitfall 5), broken async spans (Pitfall 10) | Try/except at boundary, avoid async generators, decorate all significant functions |
| Evaluators | Hallucinated APIs passing validation (Pitfall 12) | Ground judge on harvested content, cross-reference code blocks against API surface |
| CLI / Infrastructure | Dry-run gaps (Pitfall 15), checkpoint serialization (Pitfall 14) | Validate API keys in dry-run, use model_dump_json() |

---

## Sources

### Academic / Research
- [Why Do Multi-Agent LLM Systems Fail? (MAST Taxonomy)](https://arxiv.org/abs/2503.13657) -- Cemri et al. 2025, taxonomy of 1600+ failure traces across 7 MAS frameworks

### Anthropic SDK and API
- [Anthropic Structured Outputs Documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic Tool Use Implementation Guide](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)
- [Anthropic Extended Thinking Documentation](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Anthropic Adaptive Thinking Documentation](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking)
- [AsyncHttpxClientWrapper Event Loop Issue (GitHub #807)](https://github.com/anthropics/anthropic-sdk-python/issues/807)
- [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)

### LangSmith
- [LangSmith Tracing Deep Dive](https://medium.com/@aviadr1/langsmith-tracing-deep-dive-beyond-the-docs-75016c91f747) -- MEDIUM confidence
- [LangSmith @traceable Crash Issue (GitHub #1306)](https://github.com/langchain-ai/langsmith-sdk/issues/1306)
- [LangSmith Async Generator Issue (GitHub #607)](https://github.com/langchain-ai/langsmith-sdk/issues/607)

### Firecrawl
- [Firecrawl Rate Limits](https://docs.firecrawl.dev/rate-limits)
- [Firecrawl Scrape Documentation](https://docs.firecrawl.dev/features/scrape)

### Exa / Tavily
- [Exa Rate Limits](https://docs.exa.ai/reference/rate-limits)
- [Tavily Rate Limits](https://docs.tavily.com/documentation/rate-limits)
- [Exa Python SDK Specification](https://exa.ai/docs/sdks/python-sdk-specification)

### Pydantic
- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/)

### General
- [Instructor: Semantic Validation with Structured Outputs](https://python.useinstructor.com/blog/2025/05/20/understanding-semantic-validation-with-structured-outputs/)
- [Multi-Agent System Failure Analysis (Galileo)](https://galileo.ai/blog/multi-agent-llm-systems-fail)
