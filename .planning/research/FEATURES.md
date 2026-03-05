# Feature Landscape

**Domain:** Multi-agent CLI pipeline for automated skill file generation
**Researched:** 2026-03-05

## Table Stakes

Features users expect from a multi-agent CLI pipeline that produces validated artifacts. Missing any of these makes the tool feel broken, not just incomplete.

### Pipeline Orchestration

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deterministic state machine conductor | Every serious pipeline (LangGraph, CrewAI Flows) uses explicit state machines. LLM-routed orchestration is seen as fragile for production. Users expect predictable, debuggable phase transitions. | Medium | Already a project requirement. Model this as a state machine with named phases and typed transitions -- not a prompt chain. |
| Phase-based sequential execution | CrewAI, LangGraph, and every CI/CD pipeline users have seen works in phases. A linear pipeline with clear phase boundaries is the minimum viable mental model. | Low | Phases: Harvest -> Organize -> Gap-Analyze -> Synthesize -> Produce -> Evaluate -> Package |
| Checkpoint persistence at phase boundaries | LangGraph's checkpointing and CI/CD pipeline resumability set this expectation. When a pipeline costs $2-5 per run and takes 3-10 minutes, losing progress to a transient failure is unacceptable. | Medium | JSON serialization of full pipeline state at each phase boundary. Must include all intermediate outputs, not just metadata. |
| Resume from last successful checkpoint | Direct consequence of checkpointing. Users will hit rate limits, network errors, and API outages. "Re-run from where it failed" is table stakes for any multi-step process costing real money. | Medium | CLI flag like `--resume <run-id>` or `--resume latest`. Detect stale checkpoints (input changed since checkpoint). |
| Structured input specification | CLI tools require well-defined input contracts. A JSON skill brief with seed URLs, tool category, scope, and required capabilities gives users a clear, repeatable interface. | Low | JSON schema validation via Pydantic on ingest. Provide a template generator command. |

### Content Harvesting

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-source URL extraction | Users provide URLs pointing at GitHub repos, docs sites, API schemas, and blogs. Routing to the correct extraction strategy per URL type is fundamental -- a single extraction approach fails on JS-rendered docs or raw OpenAPI specs. | Medium | URL classifier -> strategy router. At minimum: Firecrawl for JS-heavy docs, direct HTTP for APIs/schemas, GitHub API for repos. |
| JavaScript-rendered page crawling | 96% of modern docs use JS rendering (React, Next.js, Docusaurus). Plain HTTP fetches return empty shells. Firecrawl handles this. Without it, the tool produces garbage for most documentation sites. | Low | Firecrawl API with JS rendering enabled. This is a service call, not a build-it-yourself feature. |
| OpenAPI/Swagger schema extraction | API accuracy is the project's core value prop. OpenAPI schemas are ground truth for API surfaces. Failing to extract and use them means hallucinated API calls -- the exact problem the project exists to solve. | Medium | Detect OpenAPI/Swagger URLs (common patterns: `/openapi.json`, `/swagger.json`, `/api-docs`). Parse with standard libraries. Cross-reference against harvested prose docs. |
| Supplemental semantic search | Seed URLs alone rarely cover everything. Exa's semantic search and Tavily's web search fill gaps by finding related content the user didn't know about. | Medium | Exa for "find similar" semantic discovery, Tavily for keyword-driven web search. Use both -- they complement rather than overlap. |
| Content deduplication | Multiple sources often contain identical or near-identical content (e.g., README mirrored on docs site). Duplicates waste tokens and confuse synthesis agents. | Low | URL-based dedup (trivial) + content hash dedup (straightforward). Version conflict detection (same API, different versions) is the harder sub-problem. |

### Multi-Agent Synthesis

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Structured agent outputs via tool_use | Every production multi-agent system enforces structured outputs. Freeform text between agents causes parsing failures, schema drift, and cascading errors. Pydantic + tool_use is the established pattern in the Anthropic SDK ecosystem. | Low | Define Pydantic models for every inter-agent boundary. Use tool_use to enforce schema. Already a project requirement. |
| Role-specialized agents | CrewAI popularized role-based agents. Having an Organizer, Gap Analyzer, Learner, Mapper, and Documenter with distinct system prompts and responsibilities produces better output than a single mega-prompt. | Medium | Each agent gets a focused system prompt, specific Pydantic output schema, and appropriate model selection (Sonnet vs Opus). |
| Gap analysis with targeted re-harvesting | The reflection loop pattern (generate -> critique -> fix) is a core agentic AI pattern in 2025-2026. Gap analysis checks harvested content against required_capabilities and loops back for more research when gaps exist. Without this, the pipeline produces skills with missing coverage. | High | Opus-powered Gap Analyzer compares organized research against the skill brief's required_capabilities. Generates targeted search queries for gaps. Loop-with-exit-condition (saturation check or max iterations). |
| Content saturation detection | Reflection loops need termination conditions or they loop forever. An LLM-driven saturation check ("do we have enough to write this skill?") prevents both under-researching and infinite loops. | Medium | LLM call that scores coverage completeness. Define clear threshold (e.g., all required_capabilities addressed with at least one authoritative source). Cap iterations (e.g., max 3 re-harvest cycles). |

### Validation

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Heuristic validators (syntax, size) | Deterministic checks that catch obvious failures before expensive LLM evaluation. Code block syntax (ast.parse), line count (<500), YAML frontmatter validity. These are fast, free, and unambiguous. | Low | Run before LLM judges. Fast-fail on broken syntax. |
| LLM-as-judge evaluation | The dominant evaluation pattern in 2025-2026. Human review doesn't scale; heuristic checks miss semantic quality. LLM judges score API accuracy, completeness, and trigger description quality. | Medium | Opus-powered judges with specific rubrics. Score on a numeric scale. Below-threshold scores trigger re-production with specific feedback attached. |
| Feedback routing back to production agents | Without corrective loops, validation is just a report card. Routing evaluator feedback (with specific critique) back to the production agents that created the artifact closes the quality loop. | Medium | Evaluator returns structured feedback (score + specific issues). Conductor routes back to appropriate production agent with feedback context. Cap re-evaluation loops (e.g., max 2 revision cycles). |

### Output and Packaging

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Valid .skill directory output | The entire point. Must produce a directory with SKILL.md (YAML frontmatter + markdown instructions, <500 lines), plus optional supporting files. Must conform to the Agent Skills open standard. | Medium | SKILL.md with required `name` and `description` frontmatter fields. SETUP.md for prerequisites. Supporting files for reference material that exceeds the 500-line SKILL.md budget. |
| Deployment scope selection | Skills can be installed at repo scope (.claude/skills/), user scope (~/.claude/skills/), or as a plugin. The tool should package for the user's chosen scope. | Low | CLI flag: `--scope repo|user|package`. Adjust output paths accordingly. |

### Error Handling

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Exponential backoff on API calls | Standard practice for any tool making external API calls. Rate limits from Anthropic, Firecrawl, Exa, and Tavily are guaranteed at scale. Without backoff, the pipeline crashes on the first 429. | Low | Use `tenacity` library with exponential backoff + jitter. Apply to all external calls (Anthropic SDK, Firecrawl, Exa, Tavily). |
| Graceful error reporting | CLI tools that crash with raw tracebacks are hostile. Users need clear error messages indicating what failed, why, and what to do about it. | Low | Catch known failure modes (auth errors, rate limits, network timeouts, invalid input). Map to human-readable messages with suggested actions. |

### Observability

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| LangSmith tracing integration | Already a project requirement. LangSmith is the path of least resistance for tracing Anthropic SDK calls -- set one env var and it works. Traces agent calls, captures inputs/outputs, measures latency and tokens. | Low | `@traceable` decorator on all agent functions. Environment variable configuration. LangSmith handles the rest. |
| Token and cost tracking (via LangSmith) | When each pipeline run costs $2-10, users need to know where the money goes. LangSmith already captures token counts per call. | Low | Offload entirely to LangSmith. Print a summary at the end of each run (total tokens, estimated cost, per-phase breakdown from LangSmith data). |

---

## Differentiators

Features that set this tool apart. Not expected, but deliver outsized value.

### Intelligence Layer

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Adaptive model routing (Sonnet vs Opus) | Most pipelines use one model for everything. Using Sonnet for high-throughput generation and Opus exclusively for judgment calls (gap analysis, LLM-as-judge) optimizes the cost/quality tradeoff. This is a meaningful cost differentiator -- Opus costs ~5x more than Sonnet. | Low | Already a project requirement. Hardcode model selection per agent role in the conductor, not via LLM routing. |
| Multi-evaluator scoring with dimension-specific rubrics | Most LLM-as-judge implementations use a single "is this good?" prompt. Using separate evaluators for API accuracy, completeness, trigger quality, and compactness catches different failure modes and produces actionable feedback. | Medium | Each evaluator has its own rubric and scoring criteria. Aggregate scores determine pass/fail. Individual dimension scores route to specific production agents for fixes. |
| Version-aware API validation | The killer differentiator for this specific tool. Cross-referencing harvested docs against OpenAPI schemas to detect version mismatches (e.g., skill references v1 API but current version is v3) prevents the most dangerous hallucination type: plausible-but-wrong API calls. | High | Compare API endpoints, parameter names, and response shapes between prose docs and schema. Flag discrepancies. This requires structured extraction from both sources. |
| Worked example generation with syntax verification | Skills with worked examples are dramatically more useful than instruction-only skills. Generating examples and then verifying their syntax (ast.parse for Python, JSON.parse for JSON, etc.) catches hallucinated code before it reaches users. | Medium | Mapper agent generates worked examples as part of SKILL.md. Heuristic validator runs syntax checks on all code blocks. Failed syntax triggers re-generation of that specific example. |

### Developer Experience

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dry-run mode | Print the fetch plan (URLs to crawl, search queries to run, estimated API calls and cost) and exit. Lets users preview what the pipeline will do before spending money. Extremely rare in multi-agent tools, extremely valued by cost-conscious users. | Low | Already a project requirement. Execute the URL classification and search query generation steps, print the plan, skip execution. Include estimated token/cost projections. |
| Skill brief template generator | A `skill-builder init` command that generates a template skill brief JSON with documented fields. Reduces the learning curve from "read the docs" to "fill in the blanks." | Low | Click subcommand that writes a template JSON with comments. Include examples for each field. |
| Rich CLI progress output | Multi-minute pipelines with no output feel broken. Phase-by-phase progress with current agent, phase completion, and running cost estimate transforms the experience. | Low | Use `rich` library for progress bars, status spinners, and structured console output. Print phase transitions, agent names, and checkpoint confirmations. |
| Run history and artifact browsing | Store all run artifacts in a structured output directory (~/.skill-builder/runs/<run-id>/). Let users list past runs, inspect intermediate outputs, and re-package from existing artifacts. | Medium | Timestamped run directories with all intermediate JSON, final .skill output, and a run manifest. CLI subcommands: `list-runs`, `inspect <run-id>`, `repackage <run-id>`. |
| Configurable agent parameters | Let power users override model selection, temperature, max tokens, and iteration limits per agent without modifying code. Config file or CLI flags. | Low | YAML/TOML config file at ~/.skill-builder/config.yaml or project-level. CLI flags override config. Sensible defaults that work without config. |

### Pipeline Resilience

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Partial harvest recovery | If 8 of 10 URLs succeed and 2 fail (e.g., 403, timeout), continue with what you have and report the failures rather than aborting. Most pipelines are all-or-nothing. | Low | Collect results with success/failure status. Report failures prominently. Continue if enough content was harvested (configurable threshold). |
| Idempotent re-runs | Running the same skill brief twice produces the same result structure (not identical LLM outputs, but the same phases execute and the same checkpoints are created). Enables debugging and comparison. | Medium | Content-hash-based cache for harvest results. Skip re-fetching URLs whose content hash matches cached version. Force-refresh flag for overrides. |
| Cost guardrails | Set a maximum spend per run. Pipeline estimates remaining cost at each phase boundary and aborts if projected spend exceeds the limit. Prevents runaway costs from gap analysis loops. | Medium | Track cumulative token usage. Estimate remaining cost based on historical per-phase costs. Warn at 80% of budget, abort at 100%. Configurable via CLI flag or config. |

---

## Anti-Features

Features to explicitly NOT build. Each would add complexity without proportional value, or would contradict the project's design philosophy.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Web UI or dashboard | Violates the "CLI only" constraint. Adds massive frontend complexity for a tool that runs once per skill. The value is in the output artifact, not in watching it generate. | Rich CLI output with `rich`. LangSmith dashboard for deep observability. |
| Interactive human gates mid-pipeline | The project is designed for fully autonomous operation. Human gates add latency and require babysitting. The validation pipeline (heuristic + LLM-as-judge) replaces human review. | Invest in better validation quality. Dry-run mode for pre-flight human review. Post-run human review of the final artifact. |
| LLM-routed orchestration | Using an LLM to decide which phase to run next adds non-determinism, latency, and cost. Every major framework (LangGraph, CrewAI) has moved toward deterministic conductors for production. | Deterministic state machine with explicit transition rules. LLMs do the thinking inside phases; the conductor handles routing. |
| Multi-tenant or cloud deployment | Local Mac tool. Cloud deployment adds auth, infra, scaling, and security concerns that are irrelevant for a single-user CLI tool. | Design for local-first. Environment variables for API keys. No server process. |
| Plugin/extension system | The pipeline has a fixed, well-defined set of phases. An extension system adds abstraction cost with near-zero benefit when the primary user is also the developer. | Direct code modification. Clear module boundaries make it easy to swap components. |
| Generic "build anything" pipeline | Tempting to generalize beyond skills. Resist. The pipeline's value comes from being opinionated about the .skill output format, validation rubrics, and Claude Code integration. Generalization dilutes every advantage. | Stay laser-focused on .skill file production. If a second artifact type is needed later, fork the pipeline. |
| Real-time streaming of agent outputs | Streaming token-by-token output from agents is complex (SSE, websockets, partial JSON) and provides no value when the output is a structured Pydantic model. Users don't need to watch the agent think. | Phase-level progress updates only. Log full agent responses to disk for debugging. |
| Automated installation into Claude Code | Auto-modifying a user's .claude/ directory is dangerous and invasive. The tool should produce the artifact; the user should install it. | Output to a staging directory. Print installation instructions. Optionally offer a `--install` flag that copies to the target scope directory with confirmation. |
| Parallel agent execution across phases | Phases have sequential dependencies (you can't synthesize before harvesting). Within-phase parallelism (e.g., parallel URL fetching in Harvest) is valuable; cross-phase parallelism is architecturally impossible. | Parallelize within Harvest phase (concurrent URL fetches). Keep phases sequential. |

---

## Feature Dependencies

```
Structured Input Spec
  |
  v
URL Classification -> Multi-Source Extraction -> Content Dedup
  |                          |                        |
  v                          v                        v
Firecrawl Crawling    OpenAPI Extraction     Semantic Search (Exa)
  |                          |                Web Search (Tavily)
  |                          |                        |
  +----------+---------------+------------------------+
             |
             v
      Content Organizer (Agent)
             |
             v
      Gap Analyzer (Agent) <--+
             |                 |
             v                 |
      Saturation Check --------+ (loop back if gaps found)
             |
             v
      Knowledge Extraction (Learner Agent)
             |
             +---> SKILL.md Drafting (Mapper Agent)
             |
             +---> SETUP.md Generation (Documenter Agent)
             |
             v
      Heuristic Validators (syntax, size, frontmatter)
             |
             v
      LLM-as-Judge Evaluators (accuracy, completeness, triggers)
             |                            |
             v                            v
      Pass -> Packaging            Fail -> Feedback Routing -> Re-production
             |
             v
      .skill Directory Output
             |
             v
      Scope-Specific Deployment
```

### Key Dependency Chains

1. **Validation requires production**: Evaluators need complete SKILL.md + SETUP.md artifacts to judge
2. **Gap analysis requires organization**: Raw harvested content must be categorized before gaps can be identified
3. **Re-harvesting requires gap analysis**: Targeted search queries come from specific gap descriptions
4. **Packaging requires validation**: Only validated artifacts should be packaged
5. **Checkpointing spans all phases**: Must be implemented at the conductor level, not per-agent
6. **Observability spans all phases**: LangSmith tracing wraps every agent call regardless of phase
7. **Cost guardrails require token tracking**: Must aggregate costs across all API calls in all phases

### Implementation Order Implications

- Build the conductor (state machine) and checkpoint system first -- everything else plugs into it
- Harvest phase is independently buildable and testable (clear inputs/outputs)
- Validation can be built and tested against hand-crafted artifacts before the production agents exist
- Observability (LangSmith) should be wired in from the first agent, not retrofitted

---

## MVP Recommendation

### Must Ship (Phase 1)

1. **Deterministic conductor with checkpointing** -- The skeleton that everything hangs on
2. **Multi-source content harvesting** -- Firecrawl + Exa + Tavily with URL routing
3. **Content organization** -- Organizer agent with structured output
4. **Gap analysis with re-harvest loop** -- The core intelligence that makes output quality viable
5. **SKILL.md + SETUP.md production** -- Mapper + Documenter agents
6. **Heuristic validation** -- Syntax, size, frontmatter checks
7. **LLM-as-judge evaluation with feedback routing** -- At least API accuracy and completeness dimensions
8. **Basic .skill packaging** -- Directory output with correct structure
9. **LangSmith tracing** -- Wire in from day one, never retrofit

### Defer to Phase 2

- **Dry-run mode**: Valuable but not blocking core functionality
- **Rich CLI progress**: Nice UX but `print()` statements work for v1
- **Run history/artifact browsing**: Store artifacts from the start, build browsing commands later
- **Cost guardrails**: Log costs from the start, build guardrails once you know actual per-run costs
- **Idempotent re-runs with caching**: Optimize after the core pipeline is proven
- **Configurable agent parameters**: Hardcode sensible defaults first

### Defer Indefinitely

- **Version-aware API validation**: High complexity, high value, but requires significant structured extraction work. Build if the first few skills reveal version mismatch as a common failure mode.
- **Skill brief template generator**: Trivially buildable anytime. Don't block on it.

---

## Sources

### Pipeline Orchestration and Multi-Agent Patterns
- [LLM Orchestration in 2026 - AI Multiple](https://research.aimultiple.com/llm-orchestration/)
- [Top AI Agent Orchestration Frameworks 2025 - Kubiya](https://www.kubiya.ai/blog/ai-agent-orchestration-frameworks)
- [Orchestration Wars: LangChain vs. Claude-Flow vs. Custom - SitePoint](https://www.sitepoint.com/agent-orchestration-framework-comparison-2026/)
- [LangGraph Review 2025 - Sider](https://sider.ai/blog/ai-tools/langgraph-review-is-the-agentic-state-machine-worth-your-stack-in-2025)
- [AI Agent Design Patterns - Microsoft Azure](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)

### Content Harvesting
- [Crawl4AI vs Firecrawl Comparison 2026 - CapSolver](https://www.capsolver.com/blog/AI/crawl4ai-vs-firecrawl)
- [Best Web Search APIs for AI 2026 - Firecrawl](https://www.firecrawl.dev/blog/best-web-search-apis)
- [Exa API 2.0 - Exa Blog](https://exa.ai/blog/exa-api-2-0)
- [Exa vs Tavily Comparison 2026 - Exa](https://exa.ai/versus/tavily)
- [Tavily 101 - Tavily Blog](https://www.tavily.com/blog/tavily-101-ai-powered-search-for-developers)

### LLM-as-Judge Evaluation
- [Agent-as-a-Judge Evaluation - arXiv](https://arxiv.org/html/2508.02994v1)
- [Multi-Agent-as-Judge - arXiv](https://arxiv.org/abs/2507.21028)
- [LLM as a Judge 2026 Guide - Label Your Data](https://labelyourdata.com/articles/llm-as-a-judge)
- [LLM as a Judge - Arize](https://arize.com/llm-as-a-judge/)

### Reflection and Gap Analysis Patterns
- [Agentic AI Reflection Pattern - Tungsten](https://www.tungstenautomation.com/learn/blog/the-agentic-ai-reflection-pattern)
- [Reflection Agents - LangChain Blog](https://blog.langchain.com/reflection-agents/)
- [7 Agentic AI Design Patterns - ML Mastery](https://machinelearningmastery.com/7-must-know-agentic-ai-design-patterns/)
- [Self-Reflection in LLMs - Nature](https://www.nature.com/articles/s44387-025-00045-3)

### Claude Code Skills Format
- [Extend Claude with Skills - Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Skill Authoring Best Practices - Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Claude Agent Skills Open Standard](https://github.com/anthropics/skills)

### Observability
- [Best LLM Observability Tools 2026 - Firecrawl](https://www.firecrawl.dev/blog/best-llm-observability-tools)
- [LangSmith Alternatives 2026 - SigNoz](https://signoz.io/comparisons/langsmith-alternatives/)

### Retry and Resilience
- [Python Retry with Tenacity - Medium](https://medium.com/@hadiyolworld007/python-retry-policies-with-tenacity-jitter-backoff-and-idempotency-that-survives-chaos-12bba4fc8d32)
- [Fault Tolerance in LLM Pipelines - Latitude](https://latitude.so/blog/fault-tolerance-llm-pipelines-techniques)
