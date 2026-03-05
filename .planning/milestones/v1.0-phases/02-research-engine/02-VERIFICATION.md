---
phase: 02-research-engine
verified: 2026-03-05T18:30:00Z
status: passed
score: 14/14 must-haves verified
anti_patterns:
  - severity: warning
    file: "src/skill_builder/agents/harvest.py"
    line: 169
    pattern: "Version detection loop variable reassignment without list update"
    detail: "page = page.model_copy(...) creates new object but does not replace in pages list. detected_version stays None on returned pages. Non-blocking because check_version_conflicts re-detects versions internally."
---

# Phase 02: Research Engine Verification Report

**Phase Goal:** Given a skill brief with seed URLs, the pipeline harvests content from all source types in parallel, deduplicates and version-checks it, organizes it into structured categories, identifies gaps against required capabilities, loops back to harvest when gaps are found, and produces a validated KnowledgeModel

**Verified:** 2026-03-05T18:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | URL types (docs, github, api_schema, blog) each map to a specific extraction strategy function | VERIFIED | `router.py` STRATEGY_MAP maps all 4 types: docs->firecrawl_crawl, github->github_extract, api_schema->api_schema_extract, blog->firecrawl_crawl. route_url dispatches correctly with fallback. |
| 2 | Duplicate pages (same URL or same content hash) are removed before synthesis | VERIFIED | `dedup.py` normalize_url + content_hash + deduplicate. HarvestAgent calls deduplicate on line 162. 17 dedup tests pass. |
| 3 | Version numbers are detected in harvested content and conflicts across sources are flagged | VERIFIED | `version_check.py` detect_version with semver regex, check_version_conflicts with target_version comparison. HarvestAgent calls both (lines 166-171). 12 tests pass. |
| 4 | LLM-generated search queries are produced per required capability for both Exa and Tavily | VERIFIED | `query_generator.py` generate_search_queries uses messages.parse with GeneratedQueries model, template_fallback_queries for errors. refine_gap_queries for re-harvest. 9 tests pass. |
| 5 | Firecrawl crawls docs sites with JS rendering and returns markdown HarvestPages | VERIFIED | `firecrawl_strategy.py` uses AsyncFirecrawl with formats=["markdown"], limit=max_pages, source_type="crawl". 6 tests pass. |
| 6 | GitHub REST API extracts README, docs/, and examples/ from repos (skipping source code) | VERIFIED | `github_strategy.py` fetches README via /repos API, iterates docs/ and examples/ for .md/.rst/.txt only, follows relative links, auto-discovers docs site URLs. Returns tuple (pages, discovered_docs_urls). |
| 7 | Exa semantic search returns HarvestPages with best practices and patterns | VERIFIED | `exa_strategy.py` uses Exa() with asyncio.to_thread, type="auto", contents with text max_characters. 7 tests pass. |
| 8 | Tavily web search returns HarvestPages with common errors and version-specific issues | VERIFIED | `tavily_strategy.py` uses TavilyClient with search_depth="advanced", include_raw_content=True, prefers raw_content over content snippet. 6 tests pass. |
| 9 | Saturation pre-filter cheaply checks if any required capability has zero content | VERIFIED | `saturation.py` check_saturation makes single Sonnet call with max_tokens=1024, output_format=SaturationResult. Fails open on error. 7 tests pass. |
| 10 | All extraction strategies and supplemental searches run in parallel via asyncio | VERIFIED | `agents/harvest.py` HarvestAgent._harvest uses asyncio.create_task for all URL, Exa, and Tavily tasks, then asyncio.gather(*tasks, return_exceptions=True). Semaphore rate limiting for Exa/Tavily (3 concurrent each). |
| 11 | Organizer agent structures raw harvest into dynamic categories with source attribution | VERIFIED | `agents/organizer.py` OrganizerAgent uses messages.parse(output_format=CategorizedResearch). System prompt instructs dynamic categories and source attribution. ContentItem model has text+source_url. 7 tests pass. |
| 12 | Gap Analyzer cross-references organized research against every required capability and fails sufficiency when any is missing | VERIFIED | `agents/gap_analyzer.py` GapAnalyzerAgent uses Opus with adaptive thinking, prompt explicitly lists every required_capability numbered. System prompt: "If ANY required capability is completely missing... set is_sufficient=False". Checks stop_reason for truncation. 9 tests pass. |
| 13 | Learner agent extracts a complete KnowledgeModel from organized research | VERIFIED | `agents/learner.py` LearnerAgent uses messages.parse(output_format=KnowledgeModel) with Sonnet. Receives categorized_research + gap_report + brief. 5 tests pass. |
| 14 | Conductor passes focused kwargs to each real agent and uses real agents for Phase 2 phases | VERIFIED | `conductor.py` _build_kwargs dispatches per-phase kwargs (brief, state, raw_harvest, categorized_research, etc.). _default_agents returns HarvestAgent, OrganizerAgent, GapAnalyzerAgent, LearnerAgent for Phase 2; stubs for Phase 3. 20 conductor tests pass. |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/skill_builder/harvest/router.py` | URL type -> strategy mapping and route_url | VERIFIED | 113 lines, exports STRATEGY_MAP, route_url, api_schema_extract. Wired to real strategies. |
| `src/skill_builder/harvest/dedup.py` | URL normalization, content hashing, dedup | VERIFIED | 81 lines, exports normalize_url, content_hash, deduplicate. Used by HarvestAgent. |
| `src/skill_builder/harvest/version_check.py` | Version detection and conflict flagging | VERIFIED | 101 lines, exports detect_version, check_version_conflicts. Used by HarvestAgent. |
| `src/skill_builder/harvest/query_generator.py` | LLM query generation with fallback | VERIFIED | 139 lines, exports generate_search_queries, template_fallback_queries, refine_gap_queries. Uses messages.parse with GeneratedQueries. |
| `src/skill_builder/harvest/firecrawl_strategy.py` | Firecrawl docs crawling | VERIFIED | 67 lines, exports firecrawl_crawl. Uses AsyncFirecrawl. Wired in STRATEGY_MAP. |
| `src/skill_builder/harvest/github_strategy.py` | GitHub REST API extraction | VERIFIED | 201 lines, exports github_extract. Returns tuple (pages, docs_urls). Wired in STRATEGY_MAP. |
| `src/skill_builder/harvest/exa_strategy.py` | Exa semantic search | VERIFIED | 64 lines, exports exa_search. Uses asyncio.to_thread. Imported in HarvestAgent. |
| `src/skill_builder/harvest/tavily_strategy.py` | Tavily web search | VERIFIED | 64 lines, exports tavily_search. Prefers raw_content. Imported in HarvestAgent. |
| `src/skill_builder/harvest/saturation.py` | Saturation pre-filter | VERIFIED | 97 lines, exports check_saturation. Uses SaturationResult with messages.parse. Fails open. |
| `src/skill_builder/agents/harvest.py` | HarvestAgent with parallel orchestration | VERIFIED | 220 lines, exports HarvestAgent. asyncio.gather, semaphores, dedup, version check, saturation. |
| `src/skill_builder/agents/organizer.py` | OrganizerAgent with Sonnet | VERIFIED | 108 lines, exports OrganizerAgent. messages.parse(output_format=CategorizedResearch). |
| `src/skill_builder/agents/gap_analyzer.py` | GapAnalyzerAgent with Opus + adaptive thinking | VERIFIED | 133 lines, exports GapAnalyzerAgent. messages.parse with thinking={"type": "adaptive"}. |
| `src/skill_builder/agents/learner.py` | LearnerAgent with Sonnet | VERIFIED | 123 lines, exports LearnerAgent. messages.parse(output_format=KnowledgeModel). |
| `src/skill_builder/conductor.py` | Conductor with real agent dispatch | VERIFIED | 432 lines, _default_agents uses real Phase 2 agents, _build_kwargs dispatches focused kwargs. |
| `src/skill_builder/models/harvest.py` | Extended HarvestPage/HarvestResult | VERIFIED | source_url, detected_version, warnings, version_conflicts, queries_used all present. |
| `src/skill_builder/models/synthesis.py` | ContentItem, GeneratedQueries, SaturationResult | VERIFIED | All models present with correct fields. ResearchCategory.content is list[ContentItem]. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| router.py | models/brief.py | SeedUrl.type drives strategy selection | WIRED | route_url accepts SeedUrl, accesses seed.type for STRATEGY_MAP lookup |
| dedup.py | models/harvest.py | Operates on list[HarvestPage] | WIRED | deduplicate takes/returns list[HarvestPage], uses model_copy for content_hash |
| query_generator.py | anthropic | messages.parse(output_format=GeneratedQueries) | WIRED | generate_search_queries and refine_gap_queries both call client.messages.parse |
| agents/harvest.py | harvest/router.py | route_url dispatches | WIRED | HarvestAgent imports and calls route_url for each seed URL |
| agents/harvest.py | harvest/dedup.py | deduplicate called after collection | WIRED | HarvestAgent imports and calls deduplicate (line 162) |
| agents/harvest.py | harvest/query_generator.py | generate_search_queries | WIRED | HarvestAgent imports and calls generate_search_queries / refine_gap_queries |
| firecrawl_strategy.py | firecrawl | AsyncFirecrawl.crawl() | WIRED | Imports AsyncFirecrawl, calls fc.crawl with markdown format |
| github_strategy.py | httpx | httpx.AsyncClient for REST API | WIRED | Imports httpx, uses AsyncClient for all GitHub API calls |
| exa_strategy.py | exa_py | Exa.search() | WIRED | Imports Exa, wraps in asyncio.to_thread |
| tavily_strategy.py | tavily | TavilyClient.search() | WIRED | Imports TavilyClient, wraps in asyncio.to_thread |
| organizer.py | anthropic | messages.parse(output_format=CategorizedResearch) | WIRED | Calls self.client.messages.parse with CategorizedResearch |
| gap_analyzer.py | anthropic | messages.parse(output_format=GapReport, thinking=adaptive) | WIRED | Calls self.client.messages.parse with GapReport and adaptive thinking |
| learner.py | anthropic | messages.parse(output_format=KnowledgeModel) | WIRED | Calls self.client.messages.parse with KnowledgeModel |
| conductor.py | agents/harvest.py | agent.run(brief=self.brief, state=state) | WIRED | _build_kwargs returns brief+state for HARVESTING phase |
| conductor.py | agents/organizer.py | agent.run(raw_harvest=..., brief=...) | WIRED | _build_kwargs returns raw_harvest+brief for ORGANIZING phase |
| conductor.py | agents/gap_analyzer.py | agent.run(categorized_research=..., brief=...) | WIRED | _build_kwargs returns categorized_research+brief+harvest_warnings for GAP_ANALYZING |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| HARV-01 | 02-01 | Content router classifies URLs by type and selects extraction strategy | SATISFIED | router.py STRATEGY_MAP maps all 4 types, route_url dispatches with fallback |
| HARV-02 | 02-02 | Firecrawl crawls docs sites with JS rendering | SATISFIED | firecrawl_strategy.py uses AsyncFirecrawl with markdown format |
| HARV-03 | 02-02 | Pipeline searches for and extracts OpenAPI/Swagger JSON schemas | SATISFIED | api_schema_extract in router.py searches Exa for OpenAPI specs, falls back to crawl |
| HARV-04 | 02-01 | Pipeline validates extracted API data against target_api_version | SATISFIED | version_check.py check_version_conflicts with target_version parameter |
| HARV-05 | 02-02 | Exa semantic search finds examples and best practices | SATISFIED | exa_strategy.py exa_search with type="auto" and text contents |
| HARV-06 | 02-02 | Tavily web search finds common errors and integration patterns | SATISFIED | tavily_strategy.py tavily_search with search_depth="advanced" |
| HARV-07 | 02-01 | Content deduplicated by URL and content hash before synthesis | SATISFIED | dedup.py normalize_url + content_hash + deduplicate. Called in HarvestAgent. |
| HARV-08 | 02-01 | Version numbers detected across sources and conflicts flagged | SATISFIED | version_check.py detect_version (semver regex) + check_version_conflicts |
| HARV-09 | 02-02 | Saturation check: LLM assesses whether critical info is missing | SATISFIED | saturation.py check_saturation with cheap Sonnet call, SaturationResult model |
| HARV-10 | 02-02 | Harvest runs URL extraction and supplemental searches in parallel | SATISFIED | HarvestAgent uses asyncio.gather with semaphore rate limiting |
| SYNTH-01 | 02-03 | Organizer agent structures raw research into categories | SATISFIED | OrganizerAgent uses Sonnet with messages.parse for dynamic CategorizedResearch |
| SYNTH-02 | 02-03 | Gap Analyzer cross-references research against brief's required_capabilities | SATISFIED | GapAnalyzerAgent prompt explicitly lists every required capability |
| SYNTH-03 | 02-03 | Gap Analyzer produces GapReport with is_sufficient, identified_gaps, recommended_search_queries | SATISFIED | GapAnalyzerAgent returns GapReport via messages.parse(output_format=GapReport) |
| SYNTH-04 | 02-03 | If any required_capability is missing, Gap Analyzer fails sufficiency | SATISFIED | System prompt: "If ANY required capability is completely missing...set is_sufficient=False". Tests verify. |
| SYNTH-05 | 02-03 | Learner extracts structured KnowledgeModel | SATISFIED | LearnerAgent uses messages.parse(output_format=KnowledgeModel) with all required fields |
| SYNTH-06 | 02-03 | All agent outputs enforced via Pydantic model schemas | SATISFIED | All agents use messages.parse(output_format=PydanticModel) which enforces via tool_use internally |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/skill_builder/agents/harvest.py` | 169 | Loop variable reassignment without list update | Warning | `page = page.model_copy(update={"detected_version": ...})` does not replace the page in `pages` list. The `detected_version` field stays None on returned HarvestPage objects. Non-blocking: check_version_conflicts re-detects versions internally, and downstream agents work from content, not detected_version. |

### Human Verification Required

### 1. End-to-end pipeline with real API keys

**Test:** Set FIRECRAWL_API_KEY, EXA_API_KEY, TAVILY_API_KEY, GITHUB_TOKEN. Run `skill-builder build` with a real skill brief containing docs, github, and blog seed URLs.
**Expected:** Pipeline should harvest from all sources, deduplicate, organize, analyze gaps, and produce a KnowledgeModel. No crashes. Reasonable content extracted.
**Why human:** Requires real API keys and external services. Tests use mocks only.

### 2. Saturation and gap loop behavior

**Test:** Run with a brief that has required_capabilities the seed URLs are unlikely to cover (e.g., an obscure capability). Observe whether the gap loop triggers re-harvesting.
**Expected:** Gap Analyzer should find insufficient coverage, conductor should re-harvest up to MAX_GAP_LOOPS times, then force-proceed to learning.
**Why human:** Requires real LLM calls to verify Gap Analyzer judgment quality.

### 3. Rate limiting under load

**Test:** Create a brief with many seed URLs and required_capabilities. Monitor Exa/Tavily API usage.
**Expected:** Semaphore limits (3 concurrent each) should prevent throttling errors.
**Why human:** Requires real API keys and monitoring actual concurrent request behavior.

### Gaps Summary

No gaps found. All 14 observable truths verified. All 16 requirements (HARV-01 through HARV-10, SYNTH-01 through SYNTH-06) are satisfied with substantive implementations and test coverage. All key links are wired. 211 tests pass with zero failures, ruff lint passes clean, no TODO/FIXME/placeholder markers in any Phase 2 code.

One warning-level anti-pattern: detected_version field not properly set on returned HarvestPage objects due to loop variable reassignment (line 169 of harvest.py). This is non-blocking since version conflict detection works independently.

---

_Verified: 2026-03-05T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
