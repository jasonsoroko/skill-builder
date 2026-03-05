# Skill Builder

## What This Is

A Python CLI tool and multi-agent orchestration pipeline that takes seed URLs and a skill brief as input, conducts deep research via Firecrawl/Exa/Tavily/GitHub, synthesizes knowledge through Sonnet and Opus agents with Pydantic-validated structured output, validates the output with heuristic and LLM-as-judge evaluators, and produces a properly formatted `.skill` file ready for installation into Claude Code. Built for local Mac use.

## Core Value

Produce skills that are accurate enough to install without manual editing -- no hallucinated APIs, no coverage gaps, no stale versions.

## Requirements

### Validated

- ✓ Accept structured skill brief (JSON) with seed URLs, tool category, scope, and required capabilities -- v1.0
- ✓ Route URLs to correct extraction strategy (GitHub repos, docs sites/SPAs, API schemas, blogs) -- v1.0
- ✓ Crawl dynamically rendered documentation using Firecrawl with JS rendering -- v1.0
- ✓ Search for and extract OpenAPI/Swagger schemas as ground truth -- v1.0
- ✓ Run supplemental semantic search via Exa and web search via Tavily -- v1.0
- ✓ Deduplicate content by URL and content hash; detect version conflicts -- v1.0
- ✓ Saturation check: LLM-driven assessment of whether critical info is missing -- v1.0
- ✓ Organize raw research into structured categories (Organizer agent, Sonnet) -- v1.0
- ✓ Cross-reference harvest against required_capabilities and flag gaps (Gap Analyzer, Opus) -- v1.0
- ✓ Loop back to harvest when gaps are found, with targeted search queries -- v1.0
- ✓ Extract structured KnowledgeModel from gap-free research (Learner agent, Sonnet) -- v1.0
- ✓ Draft SKILL.md under 500 lines with worked examples and pushy trigger description -- v1.0
- ✓ Generate SETUP.md with prerequisites, API keys, quick start, troubleshooting -- v1.0
- ✓ Validate with heuristic evaluators: compactness (<500 lines), syntax (ast.parse code blocks) -- v1.0
- ✓ Validate with LLM-as-judge evaluators: API accuracy, completeness, trigger quality (Opus) -- v1.0
- ✓ Route back to production when any evaluator scores below 7, with specific feedback -- v1.0
- ✓ Package output as .skill file for repo, user, or package deployment -- v1.0
- ✓ Deterministic state machine conductor -- not an LLM call -- v1.0
- ✓ Checkpoint persistence to JSON at every phase boundary -- v1.0
- ✓ All agent calls traced via LangSmith @traceable; cost/token tracking offloaded to LangSmith -- v1.0
- ✓ All agent outputs enforced via tool_use -> Pydantic models -- v1.0
- ✓ Exponential backoff on all external API calls -- v1.0
- ✓ Dry-run mode that prints fetch plan and exits -- v1.0
- ✓ Fully autonomous operation -- no human gates required -- v1.0

### Active

(None yet -- define with next milestone)

### Out of Scope

- Web UI -- CLI only
- Automated testing against live Claude Code sessions -- manual verification
- CI/cloud deployment -- local Mac only for now
- Interactive human gates mid-pipeline -- user wants fully autonomous runs
- Near-duplicate detection via simhash/minhash -- standard dedup sufficient for v1
- Cross-platform skill generation -- Claude Code only for now

## Context

Shipped v1.0 with 12,113 LOC Python across 122 files. 342 tests passing.
Tech stack: Python 3.12, Click, Pydantic v2, Anthropic SDK (messages.parse), Firecrawl, Exa, Tavily, LangSmith, tenacity, Rich.
Architecture: deterministic conductor state machine -> 9 agents (1 stub intake, 8 real) -> 5 evaluators.
All 46 v1 requirements satisfied across 4 phases. Milestone audit passed with zero gaps.

## Constraints

- **Model selection**: Sonnet 4.6 for generation/routing/mapping; Opus 4.6 exclusively for Gap Analyzer and LLM-as-judge evaluators. Adaptive thinking on both.
- **Output format**: Must conform to Claude Code .skill format -- SKILL.md with YAML frontmatter, <500 lines
- **Architecture**: Conductor must be a deterministic state machine, never an LLM call
- **Concurrency**: Harvest parallelized via asyncio.gather; synthesis sequential
- **Python packaging**: Proper pyproject.toml, Click CLI entry point

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fully autonomous (no human gates) | User trusts the validation pipeline and wants speed | ✓ Good -- pipeline runs end-to-end unattended |
| LangSmith for all cost/token tracking | Avoids duplicating observability locally; LangSmith already traces everything | ✓ Good -- zero local tracking code needed |
| Pydantic + tool_use for all agent outputs | Enforces structured output, prevents drift | ✓ Good -- caught schema violations during development |
| Deterministic conductor (not LLM-routed) | Predictable, testable phase transitions; LLM routing adds latency and non-determinism | ✓ Good -- conductor is fully testable with stubs |
| Local Mac only | Simplest deployment; CI can come later if needed | ✓ Good -- kept scope manageable |
| Coarse 3-phase roadmap + 1 gap-closure phase | Following pipeline data flow (Foundation -> Research -> Output + Integration Wiring) | ✓ Good -- natural decomposition, clean dependencies |
| Programmatic score >= 7 threshold override | Never trust LLM to judge its own pass/fail threshold | ✓ Good -- reliable validation gating |
| Sync SDK clients wrapped in asyncio.to_thread() | Untested async variants for Exa/Tavily were unreliable | ✓ Good -- pragmatic approach that works |
| Dynamic tracing at dispatch time (not static decorator) | Per-call metadata with iteration counts | ✓ Good -- correct phase/agent context in spans |
| _usage_meta as dynamic attribute (not Pydantic field) | Avoids schema changes and serialization side effects | ✓ Good -- clean separation of concerns |

---
*Last updated: 2026-03-05 after v1.0 milestone*
