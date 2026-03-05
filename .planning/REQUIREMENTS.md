# Requirements: Skill Builder

**Defined:** 2026-03-05
**Core Value:** Produce skills accurate enough to install without manual editing — no hallucinated APIs, no coverage gaps, no stale versions

## v1 Requirements

### Pipeline Core

- [x] **CORE-01**: User can provide a structured skill brief (JSON) with seed URLs, tool category, scope, required capabilities, and deploy target
- [x] **CORE-02**: Conductor implements a deterministic state machine with explicit phase transitions (intake → harvest → synthesis → production → validation → packaging)
- [x] **CORE-03**: Conductor routes Gap Analyzer failures back to harvest with recommended search queries (max 2 iterations)
- [x] **CORE-04**: Conductor routes validation failures back to production with evaluator feedback (max 2 iterations)
- [x] **CORE-05**: Pipeline state persists to JSON at every phase boundary in `.skill-builder/state/{tool_name}.json`
- [x] **CORE-06**: Pipeline can resume from any checkpoint after failure
- [x] **CORE-07**: Dry-run mode prints fetch plan and estimated API cost, then exits
- [x] **CORE-08**: Global token budget cap prevents runaway costs in feedback loops
- [x] **CORE-09**: CLI entry point via Click accepts brief file path and options (dry-run, resume, verbose)
- [ ] **CORE-10**: Rich CLI progress output shows current phase, agent activity, and completion status

### Content Harvest

- [x] **HARV-01**: Content router classifies URLs by type (GitHub repo, docs site/SPA, API schema, blog/tutorial) and selects extraction strategy
- [x] **HARV-02**: Firecrawl crawls docs sites with JS rendering enabled to capture dynamically generated pages
- [x] **HARV-03**: Pipeline actively searches for and extracts OpenAPI/Swagger JSON schemas as ground truth
- [x] **HARV-04**: Pipeline validates extracted API data against `target_api_version` from the brief and discards deprecated endpoints
- [x] **HARV-05**: Exa semantic search finds examples and best practices for the target tool
- [x] **HARV-06**: Tavily web search finds common errors and Claude Code integration patterns
- [x] **HARV-07**: Content is deduplicated by URL and content hash before synthesis
- [x] **HARV-08**: Version numbers are detected across sources and conflicts are flagged
- [x] **HARV-09**: Saturation check: LLM assesses whether critical information is still missing after each harvest round
- [x] **HARV-10**: Harvest phase runs URL extraction and supplemental searches in parallel

### Agent Synthesis

- [x] **SYNTH-01**: Organizer agent (Sonnet) structures raw research into categories: installation, core concepts, use cases, API surface, config, common errors, anti-patterns, integration patterns, dependencies
- [x] **SYNTH-02**: Gap Analyzer agent (Opus with adaptive thinking) cross-references organized research against the skill brief's `required_capabilities`, `target_use_case`, `tool_category`, and `target_api_version`
- [x] **SYNTH-03**: Gap Analyzer produces a GapReport with `is_sufficient`, `identified_gaps`, and `recommended_search_queries`
- [x] **SYNTH-04**: If any item from `required_capabilities` is missing, Gap Analyzer fails the sufficiency check
- [x] **SYNTH-05**: Learner agent (Sonnet) extracts a structured KnowledgeModel: canonical use cases, required parameters, common gotchas, best practices, anti-patterns, dependencies, minimum viable example, trigger phrases
- [x] **SYNTH-06**: All agent outputs are enforced via Anthropic tool_use with Pydantic model schemas

### Production

- [x] **PROD-01**: Mapper agent (Sonnet) translates KnowledgeModel into a draft SKILL.md under 500 lines
- [x] **PROD-02**: SKILL.md includes YAML frontmatter with a specific, pushy trigger description (single-line)
- [x] **PROD-03**: SKILL.md includes worked examples for all canonical use cases
- [x] **PROD-04**: Large reference sections are extracted to `references/` directory
- [x] **PROD-05**: Documenter agent (Sonnet) writes SETUP.md with prerequisites, API keys, quick start, and top 3 troubleshooting tips

### Validation

- [x] **VAL-01**: Compactness evaluator checks SKILL.md is under 500 lines
- [x] **VAL-02**: Syntax evaluator extracts code blocks and runs them through `ast.parse` to catch syntax errors
- [ ] **VAL-03**: API Accuracy evaluator (Opus, LLM-as-judge) verifies every endpoint, class name, and CLI flag exists exactly in the organized research
- [ ] **VAL-04**: Completeness evaluator (Opus, LLM-as-judge) verifies all canonical use cases have worked examples and all dependencies have installation commands
- [ ] **VAL-05**: Trigger Quality evaluator (Opus, LLM-as-judge) verifies the trigger description is specific, pushy, and covers all reference trigger phrases
- [ ] **VAL-06**: Evaluators return structured scores; any score below 7 triggers feedback routing to production

### Observability

- [x] **OBS-01**: All Anthropic API calls are wrapped with LangSmith `@traceable` decorator
- [x] **OBS-02**: Each agent run includes metadata tags for phase, agent name, and iteration number
- [x] **OBS-03**: Cost and token tracking is fully offloaded to LangSmith (no local tracking)

### Packaging

- [ ] **PKG-01**: Packager assembles output folder: SKILL.md, references/, scripts/, assets/, LICENSE.txt (MIT)
- [ ] **PKG-02**: Packager produces `.skill` file based on `deploy_target` (repo, user, or package)
- [ ] **PKG-03**: Pipeline prints installation verification instructions after packaging

### Resilience

- [x] **RES-01**: Exponential backoff on all external API calls (Anthropic, Exa, Tavily, Firecrawl)
- [x] **RES-02**: LangSmith tracing errors never block the pipeline (wrapped at integration boundary)
- [x] **RES-03**: Feedback loops have hard iteration caps (max 2 for gap analysis, max 2 for validation)

## v2 Requirements

### Enhanced DX

- **DX-01**: Run history with per-run cost summaries
- **DX-02**: Configurable parameters (model selection, max pages, iteration caps)
- **DX-03**: CI/cloud deployment support (GitHub Actions)

### Advanced Harvest

- **ADV-01**: Near-duplicate detection via simhash/minhash on extracted content
- **ADV-02**: Cross-platform skill generation (Agent Skills standard beyond Claude Code)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI | CLI-only tool; web UI adds complexity without proportional value |
| Live Claude Code testing | Manual verification; automated testing against live sessions is unreliable |
| LLM-routed orchestration | Deterministic conductor is more predictable, testable, and cost-effective |
| Interactive human gates | User wants fully autonomous runs; review the final output |
| Real-time streaming output | Agents run to completion; streaming adds complexity for minimal benefit |
| Automated skill installation | Print instructions; don't touch user's Claude Code config |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| CORE-05 | Phase 1 | Complete |
| CORE-06 | Phase 1 | Complete |
| CORE-07 | Phase 1 | Complete |
| CORE-08 | Phase 1 | Complete |
| CORE-09 | Phase 1 | Complete |
| CORE-10 | Phase 3 | Pending |
| HARV-01 | Phase 2 | Complete |
| HARV-02 | Phase 2 | Complete |
| HARV-03 | Phase 2 | Complete |
| HARV-04 | Phase 2 | Complete |
| HARV-05 | Phase 2 | Complete |
| HARV-06 | Phase 2 | Complete |
| HARV-07 | Phase 2 | Complete |
| HARV-08 | Phase 2 | Complete |
| HARV-09 | Phase 2 | Complete |
| HARV-10 | Phase 2 | Complete |
| SYNTH-01 | Phase 2 | Complete |
| SYNTH-02 | Phase 2 | Complete |
| SYNTH-03 | Phase 2 | Complete |
| SYNTH-04 | Phase 2 | Complete |
| SYNTH-05 | Phase 2 | Complete |
| SYNTH-06 | Phase 2 | Complete |
| PROD-01 | Phase 3 | Complete |
| PROD-02 | Phase 3 | Complete |
| PROD-03 | Phase 3 | Complete |
| PROD-04 | Phase 3 | Complete |
| PROD-05 | Phase 3 | Complete |
| VAL-01 | Phase 3 | Complete |
| VAL-02 | Phase 3 | Complete |
| VAL-03 | Phase 3 | Pending |
| VAL-04 | Phase 3 | Pending |
| VAL-05 | Phase 3 | Pending |
| VAL-06 | Phase 3 | Pending |
| OBS-01 | Phase 1 | Complete |
| OBS-02 | Phase 1 | Complete |
| OBS-03 | Phase 1 | Complete |
| PKG-01 | Phase 3 | Pending |
| PKG-02 | Phase 3 | Pending |
| PKG-03 | Phase 3 | Pending |
| RES-01 | Phase 1 | Complete |
| RES-02 | Phase 1 | Complete |
| RES-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 46 total
- Mapped to phases: 46
- Unmapped: 0

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-05 after roadmap creation (phase assignments updated, requirement count corrected from 40 to 46)*
