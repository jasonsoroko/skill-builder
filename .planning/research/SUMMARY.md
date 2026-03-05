# Research Summary: Skill Builder

**Domain:** Python CLI multi-agent pipeline for automated Claude Code skill generation
**Researched:** 2026-03-05
**Overall confidence:** HIGH

## Executive Summary

Skill Builder is a Python CLI tool that orchestrates multiple AI agents to research a tool's API surface from seed URLs, synthesize that research into structured knowledge, and produce a validated `.skill` file ready for installation into Claude Code. The core architectural decision -- a deterministic state machine conductor that routes between specialized agents -- is well-aligned with 2025-2026 best practices. The industry has moved away from LLM-routed orchestration toward explicit state machines for production pipelines with known phase structures.

The technology stack is mature and well-supported. Every core dependency (Anthropic SDK, Pydantic v2, Click, LangSmith, Exa, Tavily, Firecrawl) has official Python SDKs with active maintenance and recent releases (all updated within the last 3 months). The Anthropic Python SDK (v0.84.0) provides native structured output support via `tool_use` with Pydantic `model_json_schema()`, eliminating the need for third-party libraries like Instructor. Extended thinking with adaptive budgets is available for the Opus-powered agents (Gap Analyzer, LLM-as-judge evaluators), though it carries an important constraint: `tool_choice` cannot force a specific tool when thinking is enabled.

The primary risk is feedback loop runaway -- the gap analysis and validation loops can burn through hundreds of dollars if uncapped. Hard iteration limits (max 2 loops each) and a global token budget are non-negotiable guardrails that must be implemented in the conductor from day one. Secondary risks include the Anthropic `tool_use` stop_reason handling (the response contains multiple content block types that must be filtered, not indexed) and LangSmith `@traceable` crash-through (observability errors must not kill the pipeline).

The LLM-as-judge evaluation pattern using LangSmith's `evaluate()` function and the `openevals` library's `create_llm_as_judge()` provides a clean integration path for the validation pipeline. Dimension-specific evaluators (API accuracy, completeness, trigger quality) with structured scoring rubrics are the established pattern for actionable feedback routing.

## Key Findings

**Stack:** Python 3.12+, Click CLI, Anthropic SDK (direct, no LangChain), Pydantic v2 for all data models, LangSmith + openevals for tracing/evaluation, Exa + Tavily + Firecrawl for research, tenacity for retries, uv for packaging, ruff for linting.

**Architecture:** Deterministic state machine conductor with ~12 states and 2 conditional feedback loops. Agents never call other agents -- all routing goes through the conductor. Every inter-agent boundary is a typed Pydantic model. Checkpoints are JSON files at phase boundaries.

**Critical pitfall:** Feedback loop runaway (gap analysis + validation loops) can multiply costs 10-40x if uncapped. Implement hard caps (max 2 iterations) and a global token budget before building any agents.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation** - Models, conductor, checkpoint, CLI scaffold, tracing wrapper
   - Addresses: Pydantic model definitions, state machine, checkpoint persistence, Click entry point, LangSmith integration
   - Avoids: State machine missing terminal states (Pitfall 4), LangSmith crash-through (Pitfall 5), Click config errors (Pitfall 13)
   - Rationale: Everything else depends on these components. The conductor is the backbone. Models define every interface. Building these first means every subsequent phase can be tested end-to-end through the conductor.

2. **Harvest** - URL classification, Firecrawl/Exa/Tavily executors, deduplication, parallel execution
   - Addresses: Multi-source content extraction, JS-rendered crawling, semantic search, content dedup
   - Avoids: Firecrawl credit burn (Pitfall 7), Exa/Tavily cost complexity (Pitfall 8), dedup failures (Pitfall 6)
   - Rationale: Harvest is independently testable (clear inputs: URLs; clear outputs: content). Building it second means you can feed real content into the synthesis agents when they are built.

3. **Synthesis** - Organizer, Gap Analyzer (with loopback), Learner agents
   - Addresses: Content organization, gap analysis with re-harvest loop, knowledge extraction
   - Avoids: Feedback loop runaway (Pitfall 1), tool_use stop_reason bugs (Pitfall 2), extended thinking interaction bugs (Pitfall 3)
   - Rationale: Synthesis agents depend on harvested content. The Gap Analyzer's loopback to harvest is the most complex control flow in the system and needs the harvest phase to exist.

4. **Production** - Mapper, Documenter agents, .skill file packaging
   - Addresses: SKILL.md drafting, SETUP.md generation, file packaging
   - Avoids: Hallucinated APIs in output (Pitfall 12)
   - Rationale: Production agents depend on the KnowledgeModel output from synthesis. Packaging is straightforward once drafts exist.

5. **Validation** - Heuristic evaluators, LLM-as-judge evaluators, feedback routing to production
   - Addresses: Syntax checking, API accuracy scoring, completeness scoring, feedback loops
   - Avoids: Unbounded validation loops (Pitfall 4), hallucinated APIs passing validation (Pitfall 12)
   - Rationale: Validation needs complete artifacts to evaluate. Building it last means you can test evaluators against manually-crafted artifacts or real pipeline output.

6. **Polish** - Dry-run mode, rich CLI output, cost guardrails, configurable parameters
   - Addresses: Developer experience, cost control, power user configurability
   - Rationale: These are valuable but not blocking core functionality. The pipeline works without them.

**Phase ordering rationale:**
- Foundation must come first because every component depends on models and the conductor
- Harvest before Synthesis because synthesis agents need real content to process
- Synthesis before Production because production agents need the KnowledgeModel
- Production before Validation because evaluators need artifacts to evaluate
- Validation after Production because the feedback loop routes back to production agents
- Polish is independent and can be slotted in anywhere after Foundation

**Research flags for phases:**
- Phase 3 (Synthesis): Likely needs deeper research on extended thinking + tool_use interaction constraints when implementing the Gap Analyzer. The `tool_choice` limitation with thinking enabled is a real constraint that affects the agent base class design.
- Phase 5 (Validation): Needs deeper research on openevals `create_llm_as_judge()` API specifics and how to structure dimension-specific rubrics. The openevals library is young (v0.0.11) and may change.
- Phase 1 (Foundation): Standard patterns, unlikely to need additional research. The state machine, Pydantic models, Click CLI, and checkpoint store are well-understood.
- Phase 2 (Harvest): Standard patterns for each SDK. The main unknown is optimal Firecrawl crawl configuration (page limits, JS rendering options, timeout values) which is best determined empirically.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI. All SDKs official and actively maintained. No experimental dependencies. |
| Features | HIGH | Feature landscape is well-defined by PROJECT.md. Table stakes and differentiators are clear. |
| Architecture | HIGH | Deterministic conductor pattern is well-established. Directory structure and component boundaries are straightforward. |
| Pitfalls | HIGH | Critical pitfalls (loop runaway, tool_use handling, thinking constraints) are documented in official Anthropic docs. LangSmith pitfalls confirmed via GitHub issues. |
| Anthropic SDK | HIGH | Official SDK, v0.84.0, thoroughly documented. tool_use and extended thinking APIs are stable. |
| LangSmith SDK | MEDIUM | SDK versions move fast (0.1 -> 0.7 in under a year). @traceable and evaluate() are stable, but pin loosely. |
| openevals | MEDIUM | Young library (v0.0.11), but official LangChain project. API may change. |
| Research APIs (Exa/Tavily/Firecrawl) | HIGH | All official SDKs with clear documentation. Pricing/rate limits well-documented. |

## Gaps to Address

- **Anthropic model IDs for Sonnet 4.6 and Opus 4.6**: The exact model identifier strings (e.g., `claude-sonnet-4-6-20260XXX`) are not yet confirmed. PROJECT.md references "Sonnet 4.6" and "Opus 4.6" but the SDK requires exact model ID strings. Verify at build time.
- **openevals API stability**: The `create_llm_as_judge()` function's parameter interface should be verified against the latest openevals release before implementing Phase 5.
- **Firecrawl v4 API surface**: The firecrawl-py SDK jumped from v2 to v4. Some older documentation references v2 methods (`scrape_url`, `crawl_url`) vs v4 methods (`scrape`, `crawl`). Verify the exact method names at implementation time.
- **LangSmith tracing with Anthropic SDK**: Whether `@traceable` automatically captures Anthropic SDK token usage or requires manual instrumentation should be verified during Phase 1.
- **Exa deprecated features**: Exa recently deprecated `use_autoprompt` and the `highlights` feature. Ensure harvester code uses current API only.
