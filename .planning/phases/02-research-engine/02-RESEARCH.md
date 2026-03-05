# Phase 2: Research Engine - Research

**Researched:** 2026-03-05
**Domain:** Content harvesting (Firecrawl, Exa, Tavily, GitHub API), LLM-driven synthesis (Anthropic tool_use / structured outputs), async parallelism
**Confidence:** HIGH

## Summary

Phase 2 replaces all stub agents in the harvest and synthesis stages with real implementations. The harvest layer has four extraction strategies: Firecrawl for docs/SPA crawling, GitHub REST API for repo content, Exa for semantic search, and Tavily for factual/current search. All four run in parallel via asyncio. The synthesis layer uses three LLM agents (Organizer, Gap Analyzer, Learner) that enforce structured output via Anthropic's `messages.parse()` with Pydantic models, satisfying SYNTH-06.

The critical architectural constraint is that the Gap Analyzer (Opus with adaptive thinking) cannot use forced tool_choice -- adaptive thinking is incompatible with `tool_choice: {"type": "tool"}`. The recommended approach is `messages.parse()` with `output_format=GapReport` which uses `output_config.format` (json_schema), which IS compatible with adaptive thinking. Sonnet agents (Organizer, Learner) can use either `messages.parse()` or forced tool_use since they do not need thinking.

**Primary recommendation:** Use `client.messages.parse(output_format=PydanticModel)` for ALL agents uniformly. This is the simplest, most modern approach, works with adaptive thinking, and satisfies the SYNTH-06 requirement for Pydantic-validated structured output.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- GitHub Repo Extraction: Extract README, docs/ directory, and examples/ directory only. Skip source code files. Follow internal links from README one level deep. Auto-discover published docs sites from repo metadata/README.
- Search Query Strategy: LLM-generated queries are primary (Sonnet reads full brief). Fallback to template-based queries. Exa for semantic/conceptual search. Tavily for current/factual search. One query per required capability per tool. Gap-closure queries pass through LLM query generator.
- Version Conflicts & Missing Info: Auto-detect latest version and prefer that. Flag conflicts but proceed. Missing api_schema specs: search first, then fall back to Firecrawl crawl. Saturation check is a lightweight pre-filter (cheap Sonnet call). Version conflicts stored in HarvestResult metadata AND passed to Gap Analyzer.
- Organizer Categories: Fully dynamic categories (no fixed list). Source attribution preserved with source URL per content item.

### Claude's Discretion
- GitHub access method (REST API vs Firecrawl on rendered pages)
- Multi-tool organization strategy (per-tool sections within categories vs unified across tools)
- Gap Analyzer sufficiency evaluation approach
- Parallelization approach for harvest (asyncio, ThreadPoolExecutor, etc.)
- Content hash algorithm for deduplication
- Exact Pydantic model field changes needed for harvest warnings and source attribution

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HARV-01 | Content router classifies URLs by type and selects extraction strategy | SeedUrl.type field already provides type hints; router maps type -> strategy function |
| HARV-02 | Firecrawl crawls docs sites with JS rendering | Firecrawl `crawl()` with `formats=['markdown']` handles JS rendering natively |
| HARV-03 | Extract OpenAPI/Swagger JSON schemas as ground truth | Search via Exa/Tavily first; if not found, fall back to Firecrawl crawl per locked decision |
| HARV-04 | Validate extracted API data against target_api_version | Version detection regex + comparison logic; discard deprecated endpoints |
| HARV-05 | Exa semantic search for examples and best practices | `exa.search(query, num_results=10, contents=ContentsOptions(...))` |
| HARV-06 | Tavily web search for common errors and Claude Code patterns | `tavily.search(query, search_depth="advanced", max_results=10)` |
| HARV-07 | Deduplicate by URL and content hash | URL set + SHA-256 content hash on normalized text |
| HARV-08 | Version number detection and conflict flagging | Regex extraction + conflict metadata in HarvestResult |
| HARV-09 | Saturation check: LLM assesses missing critical info | Single cheap Sonnet call checking required_capabilities coverage |
| HARV-10 | Parallel URL extraction and supplemental searches | asyncio.gather() with async Firecrawl + httpx for GitHub + async Exa/Tavily |
| SYNTH-01 | Organizer structures raw research into categories | Sonnet + messages.parse() with CategorizedResearch model (dynamic categories) |
| SYNTH-02 | Gap Analyzer cross-references against brief | Opus + adaptive thinking + messages.parse() with GapReport model |
| SYNTH-03 | Gap Analyzer produces GapReport | GapReport model already exists with correct fields |
| SYNTH-04 | Missing required_capabilities fails sufficiency | System prompt instructs Opus to check each capability explicitly |
| SYNTH-05 | Learner extracts KnowledgeModel | Sonnet + messages.parse() with KnowledgeModel model |
| SYNTH-06 | All agent outputs enforced via tool_use with Pydantic schemas | messages.parse(output_format=PydanticModel) compiles schema to grammar |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| firecrawl-py | >=4.18,<5 | Docs site crawling with JS rendering | Only SDK that crawls SPAs to markdown with pagination |
| exa-py | >=2.7,<3 | Semantic search for best practices/patterns | Neural search optimized for conceptual queries |
| tavily-python | >=0.7,<1 | Factual web search for errors/versions | Search API optimized for AI agent RAG workflows |
| anthropic | >=0.84,<1 | LLM calls (Sonnet 4.6, Opus 4.6) | Already installed; messages.parse() for structured output |
| httpx | (transitive) | GitHub REST API calls, async HTTP | Already a dependency of anthropic SDK |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib (stdlib) | N/A | SHA-256 content hashing for dedup | HARV-07 deduplication |
| asyncio (stdlib) | N/A | Parallel harvest orchestration | HARV-10 parallel execution |
| re (stdlib) | N/A | Version number extraction from text | HARV-08 version detection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GitHub REST API via httpx | PyGithub | PyGithub adds a dependency; httpx is already transitive and sufficient for 3 endpoints |
| asyncio.gather | ThreadPoolExecutor | ThreadPoolExecutor works but asyncio is more natural for I/O-bound network calls; Firecrawl/Exa/Tavily all have async clients |
| SHA-256 for content hash | xxhash/simhash | SHA-256 is stdlib, no dependency; simhash is v2 (ADV-01) |

**Installation:**
```bash
uv add "firecrawl-py>=4.18,<5" "exa-py>=2.7,<3" "tavily-python>=0.7,<1"
```

## Architecture Patterns

### Recommended Project Structure
```
src/skill_builder/
  agents/
    base.py              # BaseAgent Protocol (existing)
    stubs.py             # Stub agents (existing, unchanged)
    harvest.py           # HarvestAgent (real implementation)
    organizer.py         # OrganizerAgent (real implementation)
    gap_analyzer.py      # GapAnalyzerAgent (real implementation)
    learner.py           # LearnerAgent (real implementation)
  harvest/
    __init__.py
    router.py            # URL type -> strategy mapping
    firecrawl_strategy.py  # Firecrawl crawl/scrape
    github_strategy.py   # GitHub REST API extraction
    exa_strategy.py      # Exa semantic search
    tavily_strategy.py   # Tavily web search
    query_generator.py   # LLM-generated search queries
    dedup.py             # URL + content hash deduplication
    version_check.py     # Version detection & conflict flagging
    saturation.py        # Lightweight saturation pre-filter
  models/
    harvest.py           # Extended HarvestPage, HarvestResult (existing, extend)
    synthesis.py         # Extended CategorizedResearch, etc. (existing, extend)
    ...
  conductor.py           # Updated to pass kwargs and use real agents
  tracing.py             # Existing (used by real agents)
  resilience.py          # Existing (used by all API calls)
```

### Pattern 1: Strategy-Based Content Router
**What:** Map URL types to extraction strategy functions
**When to use:** HARV-01 content routing
**Example:**
```python
# Source: Derived from SeedUrl.type Literal["docs", "github", "api_schema", "blog"]
from typing import Callable, Awaitable

STRATEGY_MAP: dict[str, Callable[..., Awaitable[list[HarvestPage]]]] = {
    "docs": firecrawl_crawl,
    "github": github_extract,
    "api_schema": api_schema_extract,
    "blog": firecrawl_crawl,  # blogs are just docs sites
}

async def route_url(seed: SeedUrl, max_pages: int) -> list[HarvestPage]:
    strategy = STRATEGY_MAP.get(seed.type, firecrawl_crawl)
    return await strategy(seed.url, max_pages=max_pages)
```

### Pattern 2: Parallel Harvest with asyncio.gather
**What:** Run all URL extractions and supplemental searches concurrently
**When to use:** HARV-10 parallel execution
**Example:**
```python
import asyncio

async def harvest_all(
    seed_urls: list[SeedUrl],
    exa_queries: list[str],
    tavily_queries: list[str],
    max_pages: int,
) -> list[HarvestPage]:
    # Build task list
    tasks = []
    for seed in seed_urls:
        tasks.append(route_url(seed, max_pages))
    for query in exa_queries:
        tasks.append(exa_search(query))
    for query in tavily_queries:
        tasks.append(tavily_search(query))

    # Run all in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    pages = []
    errors = []
    for result in results:
        if isinstance(result, Exception):
            errors.append(result)
        else:
            pages.extend(result)
    return pages  # errors logged, not fatal
```

### Pattern 3: Structured Output via messages.parse()
**What:** Force LLM to return Pydantic-validated models
**When to use:** ALL synthesis agents (SYNTH-01 through SYNTH-06)
**Example:**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import Anthropic

client = Anthropic()

# For Sonnet agents (Organizer, Learner):
response = client.messages.parse(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    output_format=CategorizedResearch,
    messages=[{"role": "user", "content": prompt}],
)
result: CategorizedResearch = response.parsed_output

# For Opus agent (Gap Analyzer) with adaptive thinking:
response = client.messages.parse(
    model="claude-opus-4-6",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_format=GapReport,
    messages=[{"role": "user", "content": prompt}],
)
result: GapReport = response.parsed_output
```

### Pattern 4: Agent Receives Focused Input via kwargs
**What:** Conductor passes only relevant data to each agent
**When to use:** Updating conductor._run_phase() to pass kwargs
**Example:**
```python
# In conductor._run_phase():
if phase == PipelinePhase.HARVESTING:
    result = agent.run(brief=self.brief, state=state)
elif phase == PipelinePhase.ORGANIZING:
    result = agent.run(raw_harvest=state.raw_harvest, brief=self.brief)
elif phase == PipelinePhase.GAP_ANALYZING:
    result = agent.run(
        categorized_research=state.categorized_research,
        brief=self.brief,
    )
elif phase == PipelinePhase.LEARNING:
    result = agent.run(
        categorized_research=state.categorized_research,
        gap_report=state.gap_report,
        brief=self.brief,
    )
```

### Anti-Patterns to Avoid
- **Passing entire PipelineState to agents:** Agents should receive only their focused inputs, not the whole state blob. The conductor is the only component that reads/writes PipelineState.
- **Sequential harvest:** Never fetch URLs one-by-one. Always use asyncio.gather for parallel I/O.
- **Forced tool_choice with adaptive thinking:** Using `tool_choice: {"type": "tool"}` with `thinking: {"type": "adaptive"}` will raise an API error. Use `messages.parse()` with `output_format` instead.
- **Hardcoded organizer categories:** Per locked decision, categories are fully dynamic. Do not define a fixed enum or list.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Docs site crawling with JS | Custom Selenium/Playwright scraper | Firecrawl `crawl()` | JS rendering, pagination, markdown conversion all built-in |
| Semantic web search | Custom embedding + vector search | Exa `search()` | Neural search index pre-built; handles ranking |
| Factual web search | Custom web scraping + ranking | Tavily `search()` | Optimized for AI agent RAG; returns clean snippets |
| Structured LLM output | Manual JSON parsing + validation | `messages.parse(output_format=Model)` | Grammar-constrained generation; schema-guaranteed responses |
| Content hash | Custom fingerprinting | `hashlib.sha256(content.encode()).hexdigest()` | stdlib, collision-resistant, well-understood |
| Retry with backoff | Custom sleep loops | tenacity via `api_retry()` | Already built in Phase 1 resilience.py |
| LangSmith tracing | Manual span creation | `traceable_agent()` decorator | Already built in Phase 1 tracing.py |

**Key insight:** Phase 2 is primarily an integration phase -- wiring four external APIs (Firecrawl, Exa, Tavily, GitHub) and three LLM agents together. The heavy lifting is done by the SDKs and the Anthropic structured output feature. Custom logic is limited to: content routing, dedup, version detection, query generation, and saturation checking.

## Common Pitfalls

### Pitfall 1: Forced tool_choice with Thinking
**What goes wrong:** API returns 400 error when combining `tool_choice: {"type": "tool", "name": "..."}` with `thinking: {"type": "adaptive"}`
**Why it happens:** Extended/adaptive thinking requires Claude to reason freely about tool use; forced tool selection removes that autonomy
**How to avoid:** Use `messages.parse(output_format=PydanticModel)` which uses `output_config.format` (json_schema grammar) instead of tool_choice. This IS compatible with adaptive thinking.
**Warning signs:** Error message about incompatible tool_choice and thinking parameters

### Pitfall 2: Firecrawl Timeout on Large Sites
**What goes wrong:** Firecrawl `crawl()` blocks for minutes on large documentation sites
**Why it happens:** Default timeout is 120s; large sites have hundreds of pages
**How to avoid:** Set explicit `limit` parameter matching `brief.max_pages` (default 50). Use `timeout` parameter. Wrap with tenacity retry.
**Warning signs:** HTTP timeout errors, very slow harvest phase

### Pitfall 3: Exa/Tavily Rate Limits with Many Queries
**What goes wrong:** 429 rate limit errors when sending one-query-per-capability-per-tool in parallel
**Why it happens:** Free/low-tier API plans have strict rate limits
**How to avoid:** Use `asyncio.Semaphore` to limit concurrent requests per API (e.g., max 3 concurrent Exa calls). Wrap with tenacity api_retry().
**Warning signs:** 429 errors, sudden failures partway through search phase

### Pitfall 4: Content Dedup Misses Near-Duplicates
**What goes wrong:** Same content appears multiple times because URLs differ slightly (trailing slash, query params) or content has minor variations
**Why it happens:** Exact URL matching and exact content hash miss near-duplicates
**How to avoid:** Normalize URLs (strip trailing slash, sort query params, lowercase). For content, normalize whitespace before hashing. Accept that exact-hash dedup is v1; simhash is v2 (ADV-01).
**Warning signs:** Organized research has repetitive content items

### Pitfall 5: GitHub API Rate Limits Without Auth
**What goes wrong:** GitHub API returns 403 after 60 requests/hour for unauthenticated requests
**Why it happens:** GitHub's REST API has a 60 req/hr limit without a token, 5000 req/hr with a token
**How to avoid:** Support optional `GITHUB_TOKEN` env var for authenticated requests via httpx. Fall back gracefully if not set (warn user about rate limits).
**Warning signs:** 403 responses from GitHub API

### Pitfall 6: messages.parse() Output Truncation
**What goes wrong:** LLM output truncated when max_tokens is too low, resulting in invalid JSON / parse failure
**Why it happens:** Complex structured outputs (KnowledgeModel with many fields) can be long
**How to avoid:** Set generous max_tokens (8192 for Sonnet agents, 16000 for Opus). Check `response.stop_reason == "end_turn"` (not "max_tokens").
**Warning signs:** `stop_reason: "max_tokens"` in response, parse errors

### Pitfall 7: Conductor kwargs Mismatch
**What goes wrong:** Real agents expect `brief` kwarg but conductor calls `agent.run()` with no args (current Phase 1 behavior)
**Why it happens:** Phase 1 stubs ignore kwargs; real agents need them
**How to avoid:** Update `conductor._run_phase()` to pass appropriate kwargs per phase (see Pattern 4 above). Stubs already accept `**kwargs` so backward-compatible.
**Warning signs:** TypeError about missing required arguments

## Code Examples

### Firecrawl Docs Crawl
```python
# Source: https://docs.firecrawl.dev/sdks/python
from firecrawl import AsyncFirecrawl

async def firecrawl_crawl(url: str, max_pages: int = 50) -> list[HarvestPage]:
    fc = AsyncFirecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    result = await fc.crawl(url, limit=max_pages, scrape_options={"formats": ["markdown"]})

    pages = []
    for doc in result.get("data", []):
        pages.append(HarvestPage(
            url=doc.get("url", url),
            title=doc.get("metadata", {}).get("title", ""),
            content=doc.get("markdown", ""),
            source_type="crawl",
        ))
    return pages
```

### GitHub REST API Content Extraction
```python
# Source: https://docs.github.com/en/rest/repos/contents
import httpx
import base64

async def github_extract(repo_url: str, max_pages: int = 50) -> list[HarvestPage]:
    """Extract README, docs/, and examples/ from a GitHub repo."""
    # Parse owner/repo from URL
    parts = repo_url.rstrip("/").split("/")
    owner, repo = parts[-2], parts[-1]

    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    pages = []
    async with httpx.AsyncClient(headers=headers) as client:
        # Fetch README
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if resp.status_code == 200:
            pages.append(HarvestPage(
                url=f"https://github.com/{owner}/{repo}#readme",
                title=f"{repo} README",
                content=resp.text,
                source_type="github_api",
            ))

        # Fetch docs/ and examples/ directory contents
        for directory in ["docs", "examples"]:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{directory}"
            )
            if resp.status_code == 200:
                for item in resp.json():
                    if item["type"] == "file" and item["name"].endswith((".md", ".rst", ".txt")):
                        file_resp = await client.get(
                            item["url"],
                            headers={"Accept": "application/vnd.github.raw+json"},
                        )
                        if file_resp.status_code == 200:
                            pages.append(HarvestPage(
                                url=item["html_url"],
                                title=item["name"],
                                content=file_resp.text,
                                source_type="github_api",
                            ))
    return pages
```

### Exa Semantic Search
```python
# Source: https://exa.ai/docs/sdks/python-sdk-specification
from exa_py import Exa

async def exa_search(query: str, num_results: int = 10) -> list[HarvestPage]:
    exa = Exa()  # Reads EXA_API_KEY from env
    results = exa.search(
        query,
        num_results=num_results,
        type="auto",
        contents={"text": {"max_characters": 10000}},
    )

    pages = []
    for result in results.results:
        pages.append(HarvestPage(
            url=result.url,
            title=result.title or "",
            content=result.text or "",
            source_type="exa_search",
        ))
    return pages
```

### Tavily Web Search
```python
# Source: https://docs.tavily.com/sdk/python/reference
from tavily import TavilyClient

async def tavily_search(query: str, max_results: int = 10) -> list[HarvestPage]:
    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = tavily.search(
        query,
        search_depth="advanced",
        max_results=max_results,
        include_raw_content=True,
    )

    pages = []
    for result in response.get("results", []):
        pages.append(HarvestPage(
            url=result.get("url", ""),
            title=result.get("title", ""),
            content=result.get("raw_content") or result.get("content", ""),
            source_type="tavily_search",
        ))
    return pages
```

### LLM Query Generation (Sonnet)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from pydantic import BaseModel, Field

class GeneratedQueries(BaseModel):
    exa_queries: list[str] = Field(description="Semantic search queries for Exa")
    tavily_queries: list[str] = Field(description="Factual search queries for Tavily")

def generate_search_queries(client: Anthropic, brief: SkillBrief) -> GeneratedQueries:
    prompt = f"""Generate targeted search queries for researching this tool/skill.

Tool: {brief.name}
Description: {brief.description}
Required capabilities: {', '.join(brief.required_capabilities)}
Scope: {brief.scope}

Generate one Exa query per required capability (semantic/conceptual: best practices, patterns, usage examples).
Generate one Tavily query per required capability (factual/current: error messages, version issues, gotchas).
"""
    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        output_format=GeneratedQueries,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.parsed_output
```

### Content Deduplication
```python
import hashlib
from urllib.parse import urlparse, urlencode, parse_qs

def normalize_url(url: str) -> str:
    """Normalize URL for dedup comparison."""
    parsed = urlparse(url)
    # Lowercase scheme and host, strip trailing slash, sort query params
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip("/") or "/",
        query=urlencode(sorted(parse_qs(parsed.query).items())),
        fragment="",
    )
    return normalized.geturl()

def content_hash(content: str) -> str:
    """SHA-256 hash of normalized content for dedup."""
    normalized = " ".join(content.split())  # Collapse whitespace
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def deduplicate(pages: list[HarvestPage]) -> list[HarvestPage]:
    """Remove duplicates by URL and content hash."""
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique: list[HarvestPage] = []

    for page in pages:
        norm_url = normalize_url(page.url)
        if norm_url in seen_urls:
            continue

        h = content_hash(page.content)
        if h in seen_hashes:
            continue

        page.content_hash = h
        seen_urls.add(norm_url)
        seen_hashes.add(h)
        unique.append(page)

    return unique
```

### Gap Analyzer with Adaptive Thinking (Opus)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
def run_gap_analysis(
    client: Anthropic,
    categorized_research: dict,
    brief: SkillBrief,
    harvest_warnings: list[str],
) -> GapReport:
    prompt = f"""You are analyzing research completeness for a skill about: {brief.name}

Required capabilities: {brief.required_capabilities}
Target use case: {brief.scope}
Tool category: {brief.tool_category}
Target API version: {brief.target_api_version or 'latest'}

Harvest warnings (version conflicts, missing data):
{chr(10).join(f'- {w}' for w in harvest_warnings) if harvest_warnings else 'None'}

Organized research:
{json.dumps(categorized_research, indent=2)}

For EACH required capability, determine if the research contains sufficient information.
If ANY required capability is completely missing or severely underrepresented, mark is_sufficient=False.
For each gap, provide a specific search query that would fill it.
"""

    response = client.messages.parse(
        model="claude-opus-4-6",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_format=GapReport,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.parsed_output
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Anthropic `tool_use` for structured output | `messages.parse(output_format=Model)` with json_schema grammar | Late 2025 (GA Feb 2026) | Grammar-constrained generation; no more invalid JSON |
| `thinking: {"type": "enabled", budget_tokens: N}` | `thinking: {"type": "adaptive"}` | Feb 2026 (Opus 4.6) | Claude dynamically decides thinking depth; deprecated on 4.6 models |
| `output_format` parameter | `output_config.format` (SDK still accepts `output_format` as convenience) | Feb 2026 | SDK translates internally; both work |
| Firecrawl v1 method names | Firecrawl v4+ class `Firecrawl` (not `FirecrawlApp`) | 2025 | Class renamed from `FirecrawlApp` to `Firecrawl`; method `scrape_url` -> `scrape` |
| Exa v1 `search_and_contents` | Exa v2 `search(contents=ContentsOptions(...))` | Oct 2025 | Unified search method with inline content options |

**Deprecated/outdated:**
- `FirecrawlApp` class name: now just `Firecrawl` (and `AsyncFirecrawl`)
- `exa.search_and_contents()`: merged into `exa.search()` with `contents` parameter
- `thinking: {"type": "enabled", budget_tokens: N}` on Opus 4.6/Sonnet 4.6: deprecated, use `{"type": "adaptive"}`
- `anthropic-beta: structured-outputs-2025-11-13` header: no longer required (GA)
- `output_format` parameter: still works but internally translates to `output_config.format`

## Model Configuration Reference

| Agent | Model | Thinking | Structured Output | max_tokens |
|-------|-------|----------|-------------------|------------|
| Query Generator | claude-sonnet-4-6 | None | messages.parse(output_format=GeneratedQueries) | 2048 |
| Saturation Check | claude-sonnet-4-6 | None | messages.parse(output_format=SaturationResult) | 1024 |
| Organizer | claude-sonnet-4-6 | None | messages.parse(output_format=CategorizedResearch) | 8192 |
| Gap Analyzer | claude-opus-4-6 | adaptive | messages.parse(output_format=GapReport) | 16000 |
| Learner | claude-sonnet-4-6 | None | messages.parse(output_format=KnowledgeModel) | 8192 |

## Pydantic Model Extensions

The following changes to existing models are needed:

### HarvestPage (extend)
```python
class HarvestPage(BaseModel):
    url: str
    title: str
    content: str
    source_type: str  # "crawl", "github_api", "exa_search", "tavily_search"
    content_hash: str | None = None
    # NEW fields:
    source_url: str | None = None  # Original seed URL that led to this page
    detected_version: str | None = None  # Version number if detected
```

### HarvestResult (extend)
```python
class HarvestResult(BaseModel):
    pages: list[HarvestPage] = Field(default_factory=list)
    total_pages: int = 0
    fetch_plan: dict | None = None
    # NEW fields:
    warnings: list[str] = Field(default_factory=list)  # Version conflicts, missing data
    version_conflicts: list[dict] = Field(default_factory=list)  # {source, version, url}
    queries_used: list[str] = Field(default_factory=list)  # For re-harvest traceability
```

### ResearchCategory (extend)
```python
class ContentItem(BaseModel):
    text: str
    source_url: str  # Attribution

class ResearchCategory(BaseModel):
    name: str
    content: list[ContentItem] = Field(default_factory=list)  # Changed from list[str]
```

### CategorizedResearch (extend)
```python
class CategorizedResearch(BaseModel):
    categories: list[ResearchCategory] = Field(default_factory=list)
    source_count: int = 0
    # NEW:
    tools_covered: list[str] = Field(default_factory=list)  # Which tools had content
```

## Open Questions

1. **Exa async client availability**
   - What we know: Exa v2 docs mention `AsyncExa` but exact API parity unclear
   - What's unclear: Whether all search methods have async variants
   - Recommendation: Start with sync `Exa` in `asyncio.to_thread()` as fallback; switch to `AsyncExa` if available

2. **Tavily async client availability**
   - What we know: Tavily docs list `AsyncTavilyClient` with matching methods
   - What's unclear: Reliability of async variant in practice
   - Recommendation: Use `AsyncTavilyClient` directly; fall back to sync + `to_thread()` if issues

3. **Firecrawl crawl() response shape**
   - What we know: Returns paginated data; Python SDK auto-paginates
   - What's unclear: Exact response dict structure (keys may vary between crawl/scrape)
   - Recommendation: Access via `.get("data", [])` with defensive defaults; verify at implementation time

4. **messages.parse() with adaptive thinking**
   - What we know: Structured outputs work with adaptive thinking (grammar applies only to output, not thinking)
   - What's unclear: Whether `.parsed_output` properly handles thinking blocks in response
   - Recommendation: HIGH confidence this works (official docs confirm grammar + thinking compatibility); verify at implementation time

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x --timeout=10` |
| Full suite command | `uv run pytest tests/ --timeout=30` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARV-01 | URL type routing to correct strategy | unit | `uv run pytest tests/test_harvest_router.py -x` | Wave 0 |
| HARV-02 | Firecrawl crawl returns markdown pages | unit (mocked) | `uv run pytest tests/test_firecrawl_strategy.py -x` | Wave 0 |
| HARV-03 | API schema extraction with search fallback | unit (mocked) | `uv run pytest tests/test_harvest_router.py::test_api_schema_fallback -x` | Wave 0 |
| HARV-04 | Version validation discards deprecated endpoints | unit | `uv run pytest tests/test_version_check.py -x` | Wave 0 |
| HARV-05 | Exa search returns HarvestPages | unit (mocked) | `uv run pytest tests/test_exa_strategy.py -x` | Wave 0 |
| HARV-06 | Tavily search returns HarvestPages | unit (mocked) | `uv run pytest tests/test_tavily_strategy.py -x` | Wave 0 |
| HARV-07 | Dedup by URL and content hash | unit | `uv run pytest tests/test_dedup.py -x` | Wave 0 |
| HARV-08 | Version detection and conflict flagging | unit | `uv run pytest tests/test_version_check.py -x` | Wave 0 |
| HARV-09 | Saturation pre-filter LLM check | unit (mocked) | `uv run pytest tests/test_saturation.py -x` | Wave 0 |
| HARV-10 | Parallel harvest via asyncio | integration (mocked) | `uv run pytest tests/test_harvest_agent.py::test_parallel -x` | Wave 0 |
| SYNTH-01 | Organizer produces dynamic categories | unit (mocked) | `uv run pytest tests/test_organizer_agent.py -x` | Wave 0 |
| SYNTH-02 | Gap Analyzer checks required_capabilities | unit (mocked) | `uv run pytest tests/test_gap_analyzer_agent.py -x` | Wave 0 |
| SYNTH-03 | GapReport has correct fields | unit | `uv run pytest tests/test_models.py::test_gap_report -x` | Exists |
| SYNTH-04 | Missing capability fails sufficiency | unit (mocked) | `uv run pytest tests/test_gap_analyzer_agent.py::test_missing_capability -x` | Wave 0 |
| SYNTH-05 | Learner produces KnowledgeModel | unit (mocked) | `uv run pytest tests/test_learner_agent.py -x` | Wave 0 |
| SYNTH-06 | All outputs Pydantic-validated | unit | `uv run pytest tests/test_models.py -x` | Partially exists |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x --timeout=10`
- **Per wave merge:** `uv run pytest tests/ --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_harvest_router.py` -- covers HARV-01, HARV-03
- [ ] `tests/test_firecrawl_strategy.py` -- covers HARV-02
- [ ] `tests/test_exa_strategy.py` -- covers HARV-05
- [ ] `tests/test_tavily_strategy.py` -- covers HARV-06
- [ ] `tests/test_dedup.py` -- covers HARV-07
- [ ] `tests/test_version_check.py` -- covers HARV-04, HARV-08
- [ ] `tests/test_saturation.py` -- covers HARV-09
- [ ] `tests/test_harvest_agent.py` -- covers HARV-10 (integration with mocked APIs)
- [ ] `tests/test_organizer_agent.py` -- covers SYNTH-01
- [ ] `tests/test_gap_analyzer_agent.py` -- covers SYNTH-02, SYNTH-04
- [ ] `tests/test_learner_agent.py` -- covers SYNTH-05
- [ ] `tests/test_query_generator.py` -- covers search query generation
- [ ] Install new deps: `uv add "firecrawl-py>=4.18,<5" "exa-py>=2.7,<3" "tavily-python>=0.7,<1"`

## Sources

### Primary (HIGH confidence)
- [Firecrawl Python SDK docs](https://docs.firecrawl.dev/sdks/python) - Class names, method signatures, crawl/scrape API
- [Exa Python SDK specification](https://exa.ai/docs/sdks/python-sdk-specification) - Search API, ContentsOptions, version 2.x
- [Tavily Python SDK reference](https://docs.tavily.com/sdk/python/reference) - TavilyClient, search/extract methods
- [Anthropic Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - messages.parse(), output_config.format, Pydantic integration
- [Anthropic Adaptive Thinking docs](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking) - thinking: {"type": "adaptive"}, effort levels, tool_use compatibility
- [Anthropic Extended Thinking docs](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) - tool_choice limitations with thinking
- [GitHub REST API contents](https://docs.github.com/en/rest/repos/contents) - Repository content endpoints

### Secondary (MEDIUM confidence)
- [PyPI firecrawl-py 4.18.0](https://pypi.org/project/firecrawl-py/) - Latest version verification
- [PyPI exa-py 2.7.0](https://pypi.org/project/exa-py/) - Latest version verification
- [PyPI tavily-python 0.7.22](https://pypi.org/project/tavily-python/) - Latest version verification
- [Anthropic SDK DeepWiki](https://deepwiki.com/anthropics/anthropic-sdk-python/7.1-tool-definitions-and-parameters) - Tool definitions and parameters

### Tertiary (LOW confidence)
- Exa async client (`AsyncExa`) availability not independently verified -- docs mention it but no code example seen
- Firecrawl crawl() response exact dict shape -- inferred from SDK examples, not tested

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified on PyPI with recent releases, API methods confirmed via official docs
- Architecture: HIGH - Patterns derived from existing codebase patterns (BaseAgent Protocol, conductor dispatch) and official SDK examples
- Pitfalls: HIGH - tool_choice+thinking limitation confirmed via official Anthropic docs; rate limits are well-documented
- Model extensions: MEDIUM - Field additions are straightforward but exact naming is Claude's discretion
- Async client availability: LOW - Exa async client not independently verified

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days -- these libraries are actively developed but APIs are stable)
