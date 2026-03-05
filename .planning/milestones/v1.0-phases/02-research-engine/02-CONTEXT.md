# Phase 2: Research Engine - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Given a skill brief with seed URLs, harvest content from all source types in parallel, deduplicate and version-check it, organize it into structured categories, identify gaps against required capabilities, loop back to harvest when gaps are found, and produce a validated KnowledgeModel. Replaces all Phase 2 stub agents with real implementations.

</domain>

<decisions>
## Implementation Decisions

### GitHub Repo Extraction
- Extract README, docs/ directory, and examples/ directory only. Skip source code files.
- Follow internal links from README one level deep (e.g., README links to docs/GUIDE.md, fetch that, but don't follow links from GUIDE.md further).
- Auto-discover published docs sites: check repo metadata and README for GitHub Pages, ReadTheDocs, or similar docs site URLs. If found, add them to the crawl queue as docs-type URLs for Firecrawl.
- Implementation approach for GitHub access (API vs crawl) is Claude's discretion.

### Search Query Strategy
- LLM-generated queries are primary. An LLM (Sonnet) reads the full brief and generates targeted search queries for both Exa and Tavily. If LLM call fails, fall back to template-based queries from brief fields (name + required_capabilities).
- Exa and Tavily serve different roles: Exa for semantic/conceptual search (best practices, patterns, usage examples). Tavily for current/factual search (error messages, version-specific issues, Claude Code integration patterns).
- Number of queries per tool scales with required_capabilities: one query per required capability per tool. More capabilities = more queries.
- For gap-closure re-harvest: pass the Gap Analyzer's recommended_search_queries through the LLM query generator to produce better search-optimized queries before running them.

### Version Conflicts & Missing Info
- When sources disagree on API versions, auto-detect latest version and prefer that. Flag the conflict in output but proceed with latest.
- When a seed URL typed as api_schema has no OpenAPI/Swagger spec: first search for the spec via Exa/Tavily. If still not found, fall back to crawling the URL as a docs site with Firecrawl.
- Saturation check (HARV-09) is a lightweight pre-filter: runs after harvest as a cheap LLM check. If obviously incomplete (e.g., zero content for a required capability), re-harvest immediately without waiting for full synthesis. The Gap Analyzer (Opus) is the deeper, requirement-by-requirement quality gate that runs after the Organizer.
- Version conflicts and harvest warnings are stored in HarvestResult metadata AND passed explicitly to the Gap Analyzer so it can factor conflicts into its sufficiency assessment.

### Organizer Categories
- Fully dynamic categories: the Organizer reads the harvested content and decides what categories make sense. No fixed list. Maximum flexibility per tool/skill.
- Source attribution preserved: every content item tagged with its source URL. Helps Gap Analyzer and Learner trace claims back to sources.

### Claude's Discretion
- GitHub access method (REST API vs Firecrawl on rendered pages)
- Multi-tool organization strategy (per-tool sections within categories vs unified across tools)
- Gap Analyzer sufficiency evaluation approach (how it checks coverage against required_capabilities with dynamic categories)
- Parallelization approach for harvest (asyncio, ThreadPoolExecutor, etc.)
- Content hash algorithm for deduplication
- Exact Pydantic model field changes needed for harvest warnings and source attribution

</decisions>

<specifics>
## Specific Ideas

- The first target skill (Exa + Tavily + Firecrawl) is meta: skill-builder uses the same three tools it's building a skill for. Good for dogfooding.
- The saturation pre-filter should be genuinely cheap -- a single short Sonnet call, not a full analysis. Think "are any required capabilities completely unrepresented in the harvested content?" not "is the research sufficient?"
- Exa semantic search should lean toward finding usage patterns and best practices. Tavily should lean toward finding gotchas, error messages, and version-specific issues.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HarvestPage` model (url, title, content, source_type, content_hash): needs extension for source attribution and version info
- `HarvestResult` model (pages, total_pages, fetch_plan): needs extension for warnings/conflicts metadata
- `CategorizedResearch` model (categories, source_count): needs extension for source attribution per content item
- `GapReport` model (is_sufficient, identified_gaps, recommended_search_queries): ready to use as-is
- `KnowledgeModel` model: ready to use as-is for Learner output
- `BaseAgent` Protocol (run(**kwargs) -> BaseModel | dict): real agents must conform to this
- All stub agents provide fixture data showing expected input/output shapes

### Established Patterns
- Conductor dispatches agents via `_PHASE_AGENT_MAP` dict -- real agents replace stubs in this map
- `_store_result()` maps phase -> state field -- already handles all Phase 2 outputs
- `_resolve_gap_transition()` handles the gap loop -- already works with GapReport model
- `@traceable` LangSmith decorator pattern for all Anthropic calls (from Phase 1 tracing.py)
- Exponential backoff via tenacity for all external API calls (from Phase 1 resilience.py)
- Token budget tracking via `TokenBudget` class (budget.py)

### Integration Points
- Real agents replace stubs in `conductor.py` `_default_agents()` function
- Conductor calls `agent.run()` with no args currently -- real agents need brief/state input passed via kwargs
- Checkpoint persistence already handles all Phase 2 state fields (raw_harvest, categorized_research, gap_report, knowledge_model)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 02-research-engine*
*Context gathered: 2026-03-05*
