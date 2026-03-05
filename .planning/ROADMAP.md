# Roadmap: Skill Builder

## Overview

Skill Builder delivers a fully autonomous CLI pipeline that transforms seed URLs and a skill brief into a validated `.skill` file. The roadmap follows the pipeline's natural data flow: first build the conductor backbone and infrastructure that everything plugs into, then the research engine that gathers and synthesizes knowledge, then the output pipeline that drafts, validates, and packages the final artifact. Three phases, each delivering a complete, independently verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Conductor state machine, Pydantic models, checkpoint persistence, CLI scaffold, tracing, and resilience patterns
- [ ] **Phase 2: Research Engine** - URL classification, multi-source content extraction, parallel harvest, agent synthesis with gap analysis loopback
- [ ] **Phase 3: Output Pipeline** - Production agents, heuristic and LLM-as-judge validation, feedback routing, packaging, and Rich CLI polish
- [x] **Phase 4: Integration Wiring** - Wire budget recording, retry decorators, tracing decorators, and fix version detection persistence (gap closure from audit) (completed 2026-03-05)

## Phase Details

### Phase 1: Foundation
**Goal**: The conductor can drive a skill-building run end-to-end through all phase transitions, persist and resume state, accept input via CLI, trace all agent calls, and enforce resilience patterns -- even though the phase-specific agents are stubs
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07, CORE-08, CORE-09, OBS-01, OBS-02, OBS-03, RES-01, RES-02, RES-03
**Success Criteria** (what must be TRUE):
  1. User can run `skill-builder build brief.json` and the conductor transitions through all phases (intake, harvest, synthesis, production, validation, packaging) with stub agents, printing each transition
  2. User can kill the process mid-run, then run `skill-builder build brief.json --resume` and execution picks up from the last completed phase checkpoint
  3. User can run `skill-builder build brief.json --dry-run` and see a fetch plan with estimated API costs without any external calls being made
  4. All Anthropic API calls during a run appear as traced spans in LangSmith with phase/agent/iteration metadata, and a LangSmith tracing failure does not crash the pipeline
  5. Any simulated external API failure triggers exponential backoff retries (visible in logs), and the global token budget cap halts execution when exceeded
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md -- Project scaffold, Pydantic data models, example brief, test infrastructure
- [x] 01-02-PLAN.md -- Checkpoint store, token budget, LangSmith tracing, resilience, stub agents
- [ ] 01-03-PLAN.md -- Conductor state machine and Click CLI entry point

### Phase 2: Research Engine
**Goal**: Given a skill brief with seed URLs, the pipeline harvests content from all source types in parallel, deduplicates and version-checks it, organizes it into structured categories, identifies gaps against required capabilities, loops back to harvest when gaps are found, and produces a validated KnowledgeModel
**Depends on**: Phase 1
**Requirements**: HARV-01, HARV-02, HARV-03, HARV-04, HARV-05, HARV-06, HARV-07, HARV-08, HARV-09, HARV-10, SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04, SYNTH-05, SYNTH-06
**Success Criteria** (what must be TRUE):
  1. User provides a brief with mixed URL types (GitHub repo, docs site, API schema, blog) and the pipeline correctly routes each to its extraction strategy, running URL-based extractions and supplemental searches (Exa, Tavily) in parallel
  2. Duplicate content (same URL or same content hash) appears only once in the organized research, and version conflicts across sources are flagged in the output
  3. The Organizer agent produces structured categories (installation, core concepts, API surface, common errors, etc.) from raw harvested content, and the Gap Analyzer identifies any missing required capabilities
  4. When the Gap Analyzer finds gaps, the conductor loops back to harvest with targeted search queries, and the gap-harvest loop executes at most 2 iterations before proceeding
  5. The Learner agent produces a KnowledgeModel with all required fields (canonical use cases, parameters, gotchas, best practices, trigger phrases, etc.) and all agent outputs are Pydantic-validated via tool_use
**Plans:** 3 plans

Plans:
- [ ] 02-01-PLAN.md -- Model extensions, dependencies, harvest utilities (router, dedup, version check, query generator)
- [ ] 02-02-PLAN.md -- Extraction strategies (Firecrawl, GitHub, Exa, Tavily), saturation check, HarvestAgent
- [ ] 02-03-PLAN.md -- Synthesis agents (Organizer, Gap Analyzer, Learner), conductor wiring

### Phase 3: Output Pipeline
**Goal**: The pipeline takes a KnowledgeModel and produces a validated, packaged `.skill` file -- drafting SKILL.md and SETUP.md, running heuristic and LLM-as-judge evaluators, routing failures back to production, and assembling the final package with Rich CLI progress throughout
**Depends on**: Phase 2
**Requirements**: PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, PKG-01, PKG-02, PKG-03, CORE-10
**Success Criteria** (what must be TRUE):
  1. The Mapper agent produces a SKILL.md under 500 lines with YAML frontmatter (including a pushy trigger description), worked examples for all canonical use cases, and large reference sections extracted to a `references/` directory
  2. The Documenter agent produces a SETUP.md with prerequisites, API keys, quick start, and top 3 troubleshooting tips
  3. Heuristic evaluators catch compactness violations (over 500 lines) and syntax errors (invalid Python in code blocks), and LLM-as-judge evaluators (Opus) score API accuracy, completeness, and trigger quality -- any score below 7 triggers feedback routing back to production (max 2 iterations)
  4. The Packager assembles the output folder (SKILL.md, SETUP.md, references/, scripts/, assets/, LICENSE.txt) and produces a `.skill` file matching the brief's deploy target (repo, user, or package), with installation verification instructions printed after completion
  5. Rich CLI output shows the current phase, active agent, iteration counts, and evaluator scores throughout the entire pipeline run
**Plans:** 3 plans

Plans:
- [ ] 03-01-PLAN.md -- Production agents (Mapper, Documenter), SkillDraft model extension, heuristic evaluators (compactness, syntax)
- [ ] 03-02-PLAN.md -- LLM-as-judge evaluators (API accuracy, completeness, trigger quality), ValidatorAgent, conductor feedback wiring
- [ ] 03-03-PLAN.md -- PackagerAgent, Rich CLI progress display, conductor and CLI integration

### Phase 4: Integration Wiring
**Goal**: Wire existing tested infrastructure (budget recording, retry decorators, tracing decorators) into production code so that budget enforcement halts on exceeded, all external API calls retry on transient failure, all agent runs emit LangSmith spans with metadata, and version detection persists on HarvestPage objects
**Depends on**: Phase 3
**Requirements**: CORE-08, RES-01, OBS-02, HARV-08
**Gap Closure:** Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. Running a pipeline with a budget cap of $0.01 causes the conductor to halt after the first real API call because TokenBudget.record_usage() is called with actual response.usage data and budget.exceeded returns True
  2. Killing a Firecrawl/Exa/Tavily API endpoint (simulated via mock raising transient error) triggers exponential backoff retries visible in logs before the call succeeds or exhausts retries
  3. Every agent.run() call creates a LangSmith span with phase, agent_name, and iteration metadata tags (visible when LangSmith is configured; no-op when not)
  4. After harvest, every HarvestPage in HarvestResult.pages has detected_version populated when the content contains a semver string
**Plans:** 2/2 plans complete

Plans:
- [ ] 04-01-PLAN.md -- Extend unified retry to all SDKs, apply to strategy functions, fix version detection persistence
- [ ] 04-02-PLAN.md -- Wire budget recording in agents and conductor, apply dynamic tracing decoration

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-03-05 |
| 2. Research Engine | 3/3 | Complete | 2026-03-05 |
| 3. Output Pipeline | 3/3 | Complete | 2026-03-05 |
| 4. Integration Wiring | 2/2 | Complete   | 2026-03-05 |
