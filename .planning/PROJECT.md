# Skill Builder

## What This Is

A Python CLI tool and multi-agent orchestration pipeline that takes seed URLs and a skill brief as input, conducts deep research, synthesizes knowledge through multiple AI agents, validates the output with LLM-as-judge evaluators, and produces a properly formatted `.skill` file ready for installation into Claude Code at repo or user scope. Built for local Mac use.

## Core Value

Produce skills that are accurate enough to install without manual editing — no hallucinated APIs, no coverage gaps, no stale versions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Accept structured skill brief (JSON) with seed URLs, tool category, scope, and required capabilities
- [ ] Route URLs to correct extraction strategy (GitHub repos, docs sites/SPAs, API schemas, blogs)
- [ ] Crawl dynamically rendered documentation using Firecrawl with JS rendering
- [ ] Search for and extract OpenAPI/Swagger schemas as ground truth
- [ ] Run supplemental semantic search via Exa and web search via Tavily
- [ ] Deduplicate content by URL and content hash; detect version conflicts
- [ ] Saturation check: LLM-driven assessment of whether critical info is missing
- [ ] Organize raw research into structured categories (Organizer agent, Sonnet)
- [ ] Cross-reference harvest against required_capabilities and flag gaps (Gap Analyzer, Opus with adaptive thinking)
- [ ] Loop back to harvest when gaps are found, with targeted search queries
- [ ] Extract structured KnowledgeModel from gap-free research (Learner agent, Sonnet)
- [ ] Draft SKILL.md under 500 lines with worked examples and pushy trigger description (Mapper agent)
- [ ] Generate SETUP.md with prerequisites, API keys, quick start, troubleshooting (Documenter agent)
- [ ] Validate with heuristic evaluators: compactness (<500 lines), syntax (ast.parse code blocks)
- [ ] Validate with LLM-as-judge evaluators: API accuracy, completeness, trigger quality (Opus)
- [ ] Route back to production when any evaluator scores below 7, with specific feedback
- [ ] Package output as .skill file for repo, user, or package deployment
- [ ] Deterministic state machine conductor — not an LLM call
- [ ] Checkpoint persistence to JSON at every phase boundary
- [ ] All agent calls traced via LangSmith @traceable; cost/token tracking offloaded to LangSmith
- [ ] All agent outputs enforced via tool_use → Pydantic models
- [ ] Exponential backoff on all external API calls
- [ ] Dry-run mode that prints fetch plan and exits
- [ ] Fully autonomous operation — no human gates required (run end-to-end)

### Out of Scope

- Web UI — CLI only
- Automated testing against live Claude Code sessions — manual verification
- CI/cloud deployment — local Mac only for now
- Interactive human gates mid-pipeline — user wants fully autonomous runs

## Context

- The user is building Claude Code skills to shape Claude's behavior on specific tools and workflows. Skills are high-leverage: a gap or hallucination in a skill compounds every time Claude consults it.
- The user is early in skill authoring (1-2 built manually) and has already hit all the common failure modes: missing capabilities, hallucinated APIs, stale API versions.
- First target skill: a deep research crawling skill for Exa + Tavily + Firecrawl used together. This is meta — skill-builder depends on the same three tools.
- The tool uses three research APIs (Exa, Tavily, Firecrawl), the Anthropic SDK for agents, and LangSmith for tracing and evaluation.

## Constraints

- **Model selection**: Sonnet 4.6 for generation/routing/mapping; Opus 4.6 exclusively for Gap Analyzer and Phase 4 LLM-as-judge evaluators. Adaptive thinking on both.
- **Output format**: Must conform to Claude Code .skill format — SKILL.md with YAML frontmatter, <500 lines
- **Architecture**: Conductor must be a deterministic state machine, never an LLM call
- **Concurrency**: Phase 1 (harvest) parallelized; Phase 2 (synthesis) sequential
- **Python packaging**: Proper pyproject.toml, Click CLI entry point

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fully autonomous (no human gates) | User trusts the validation pipeline and wants speed | — Pending |
| LangSmith for all cost/token tracking | Avoids duplicating observability locally; LangSmith already traces everything | — Pending |
| Pydantic + tool_use for all agent outputs | Enforces structured output, prevents drift | — Pending |
| Deterministic conductor (not LLM-routed) | Predictable, testable phase transitions; LLM routing adds latency and non-determinism | — Pending |
| Local Mac only | Simplest deployment; CI can come later if needed | — Pending |

---
*Last updated: 2026-03-05 after initialization*
