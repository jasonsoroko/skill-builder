# Technology Stack

**Project:** Skill Builder
**Researched:** 2026-03-05
**Overall Confidence:** HIGH

## Python Version

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | >=3.12, <3.15 | Runtime | 3.12 is the floor (all dependencies require >=3.10; 3.12 gives full Pydantic v2 performance, improved error messages, and f-string improvements). 3.13 or 3.14 both work; pin floor at 3.12 for widest compat among deps. |

**Confidence:** HIGH -- All target dependencies support 3.12+. Python 3.14.3 is the newest stable release (Feb 2026). Setting floor at 3.12 avoids edge-case issues with 3.14's free-threading mode while keeping modern features.

---

## Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Click | >=8.3,<9 | CLI framework | PROJECT.md specifies Click. Battle-tested (38.7% of Python CLI projects), explicit decorator-based API, excellent for complex subcommand trees. Click 8.3.1 is current stable (Nov 2025). |
| Pydantic | >=2.12,<3 | Data models, validation | All agent outputs enforced via Pydantic models. v2 is 5-50x faster than v1 (Rust core). 2.12.5 is current stable; 2.13 is in beta. Pin >=2.12 for model_json_schema() stability and Anthropic SDK compatibility. |

**Confidence:** HIGH -- Click is explicitly chosen in PROJECT.md. Pydantic v2 is the universal standard for Python data validation in 2025-2026.

### Why Click over Typer

The PROJECT.md already specifies Click. This is the right call:
- Click is a direct dependency (Typer wraps Click anyway, adding indirection)
- The pipeline has a small CLI surface (one main command with options, maybe `run` and `dry-run` subcommands) -- Typer's type-hint magic saves nothing here
- Click's explicit decorators make the entry point self-documenting
- No need for shell completion auto-generation (Typer's main advantage)

### Why NOT argparse

- Verbose, requires manual type conversion, no built-in group/subcommand nesting
- No ecosystem plugins for progress bars, config files, etc.
- Click handles all of this out of the box

---

## AI / LLM Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| anthropic | >=0.84,<1 | Claude API client | Official Python SDK. Provides sync + async clients, tool_use, structured outputs via `client.beta.messages.parse()`, extended thinking with `budget_tokens`, and streaming. v0.84.0 released Feb 25, 2026. |

**Confidence:** HIGH -- Official SDK, actively maintained (multiple releases per month), directly from Anthropic.

### Key Anthropic SDK Patterns for This Project

**Structured output via tool_use (the pattern this project will use):**
```python
from anthropic import Anthropic
from pydantic import BaseModel

class KnowledgeModel(BaseModel):
    concepts: list[str]
    examples: list[str]
    # ...

client = Anthropic()

# Pattern 1: tool_use with forced tool_choice (PROJECT.md requirement)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    tools=[{
        "name": "output_knowledge",
        "description": "Output structured knowledge",
        "input_schema": KnowledgeModel.model_json_schema()
    }],
    tool_choice={"type": "tool", "name": "output_knowledge"},
    messages=[{"role": "user", "content": prompt}]
)
# Extract tool_use block, validate with Pydantic
tool_block = next(b for b in response.content if b.type == "tool_use")
result = KnowledgeModel.model_validate(tool_block.input)
```

**Pattern 2: Structured outputs via beta parse (newer, for strict schema guarantee):**
```python
# Uses structured-outputs-2025-11-13 beta
response = client.beta.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    messages=[{"role": "user", "content": prompt}],
    # SDK handles Pydantic -> JSON schema -> output_config
)
```

**Extended thinking (for Gap Analyzer + LLM-as-judge):**
```python
response = client.messages.create(
    model="claude-opus-4-20250514",
    max_tokens=16384,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # adaptive thinking budget
    },
    messages=[{"role": "user", "content": prompt}]
)
```

**Important constraints with extended thinking + tool_use:**
- Only supports `tool_choice: {"type": "auto"}` or `{"type": "none"}` -- cannot force a specific tool
- This means the Gap Analyzer and LLM-as-judge agents (which use Opus + extended thinking) must either: (a) use thinking WITHOUT forced tool_choice, relying on strong prompting to get structured output, or (b) use a two-pass approach (think first, then extract structured output in a second call without thinking)

**Async client:**
```python
from anthropic import AsyncAnthropic
async_client = AsyncAnthropic()
# Same API, all methods are async
response = await async_client.messages.create(...)
```

### Model Selection (per PROJECT.md)

| Agent | Model | Thinking | Rationale |
|-------|-------|----------|-----------|
| Organizer | Sonnet 4.6 | Optional | Categorization task, Sonnet is sufficient |
| Learner | Sonnet 4.6 | Optional | Extraction task, well-structured prompts suffice |
| Mapper (SKILL.md drafter) | Sonnet 4.6 | Optional | Writing task, Sonnet handles well |
| Documenter (SETUP.md) | Sonnet 4.6 | No | Straightforward generation |
| Gap Analyzer | Opus 4.6 | Yes (adaptive) | Deep reasoning required, cross-referencing capabilities |
| LLM-as-Judge evaluators | Opus 4.6 | Yes (adaptive) | Critical quality gate, needs careful reasoning |

---

## Observability / Evaluation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langsmith | >=0.7,<1 | Tracing, evaluation, cost tracking | PROJECT.md mandates LangSmith for all tracing and cost/token tracking. Provides @traceable decorator, evaluate() function, and LLM-as-judge evaluator framework. v0.7.9 is current. |
| openevals | >=0.0.11 | Prebuilt LLM-as-judge evaluators | LangChain's open-source evaluator library. Provides `create_llm_as_judge()` for custom scoring rubrics. Integrates directly with LangSmith evaluate(). |

**Confidence:** MEDIUM -- LangSmith SDK versions move fast (0.1 -> 0.4 -> 0.7 in under a year). The @traceable and evaluate() APIs are stable, but pin loosely. openevals is young but from LangChain official.

### LangSmith Integration Pattern

```python
from langsmith import traceable, Client
from langsmith.evaluation import evaluate

# Trace any function
@traceable(name="organizer_agent", tags=["phase2"])
def run_organizer(raw_content: str) -> OrganizedOutput:
    response = client.messages.create(...)
    return OrganizedOutput.model_validate(...)

# LLM-as-judge evaluation
from openevals.llm import create_llm_as_judge

api_accuracy_evaluator = create_llm_as_judge(
    prompt="Score the API accuracy of this skill file...",
    model="anthropic:claude-opus-4-20250514",
    # Returns numerical score
)

# Run evaluation
ls_client = Client()
results = evaluate(
    target_fn,
    data="dataset-name",
    evaluators=[api_accuracy_evaluator],
    experiment_prefix="skill-builder-eval"
)
```

### Environment Variables Required

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your-langsmith-api-key>
LANGCHAIN_PROJECT=skill-builder
```

---

## Research / Web APIs

### Exa (Neural / Semantic Search)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| exa-py | >=2.7,<3 | Semantic search, content retrieval | Neural search for finding semantically relevant documentation, similar pages, and extracting content. Provides search(), find_similar(), get_contents(), and answer(). v2.7.0 current. |

**Confidence:** HIGH -- Official SDK, well-documented, actively maintained.

**Key methods for this project:**
- `exa.search(query, type="auto", contents={"text": True})` -- find relevant docs by semantic meaning
- `exa.find_similar(url, contents={"text": True})` -- find pages similar to a seed URL
- `exa.get_contents(urls, text=True)` -- extract text from known URLs
- `exa.search(query, type="deep", additional_queries=[...])` -- deep search with query variations (slower, more thorough)

**Environment:** `EXA_API_KEY`

### Tavily (Web Search + Extract)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| tavily-python | >=0.7,<1 | Web search, content extraction, crawling | Broad web search (complementary to Exa's neural search). Provides search(), extract(), crawl(), and map(). Sync + async clients. v0.7.22 current (Feb 2026). |

**Confidence:** HIGH -- Official SDK, actively maintained, clear API.

**Key methods for this project:**
- `tavily.search(query, search_depth="advanced", max_results=10)` -- web search with AI-extracted snippets
- `tavily.extract(urls=["..."])` -- extract clean content from URLs
- `tavily.crawl(url, max_depth=2, limit=10)` -- crawl a site (useful for docs sites)

**Sync and async:**
```python
from tavily import TavilyClient, AsyncTavilyClient
client = TavilyClient(api_key="...")
async_client = AsyncTavilyClient(api_key="...")
```

**Environment:** `TAVILY_API_KEY`

### Firecrawl (JS-Rendered Crawling)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| firecrawl-py | >=4.14,<5 | JS-rendered scraping, deep crawling | Handles SPAs and dynamically rendered docs that Exa/Tavily cannot. Returns LLM-ready markdown. v4.18.0 current (Feb 2026). |

**Confidence:** HIGH -- Official SDK, actively maintained, well-documented.

**Key methods for this project:**
- `firecrawl.scrape(url, formats=["markdown"])` -- single page scrape with JS rendering
- `firecrawl.crawl(url, limit=20, scrape_options={"formats": ["markdown"]})` -- multi-page crawl
- Async: crawl returns a job ID; poll with `firecrawl.get_crawl_status(job_id)` or use async crawl

**Environment:** `FIRECRAWL_API_KEY`

### Research API Strategy

| Scenario | Primary Tool | Fallback |
|----------|-------------|----------|
| Seed URL is a docs site / SPA | Firecrawl (JS rendering) | Tavily extract |
| Seed URL is a GitHub repo | Exa get_contents + GitHub raw URLs | Tavily extract |
| Need to find related docs | Exa search (neural/semantic) | Tavily search |
| Need broad web results | Tavily search (web search) | Exa search |
| Need API schema / OpenAPI spec | Direct HTTP fetch + Exa search | Tavily search |
| Need to crawl an entire docs site | Firecrawl crawl | Tavily crawl |

---

## Async / Concurrency

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| asyncio | stdlib | Async orchestration | Standard library, all SDKs support it natively. Phase 1 (harvest) parallelization. |
| httpx | (transitive via anthropic) | HTTP client | Already a dependency of the Anthropic SDK. Use for any direct HTTP calls (e.g., fetching OpenAPI specs). Do NOT add aiohttp separately. |

**Confidence:** HIGH -- asyncio is stdlib. httpx is already pulled in transitively.

### Why httpx, NOT aiohttp

- The Anthropic SDK already depends on httpx -- adding aiohttp creates a second HTTP stack
- httpx supports both sync and async in one library
- For this project's concurrency needs (10-20 parallel API calls during harvest), httpx is more than sufficient
- aiohttp only makes sense at 1000+ concurrent connections

### Concurrency Pattern

```python
import asyncio
from anthropic import AsyncAnthropic

async def harvest_parallel(urls: list[str]) -> list[Content]:
    """Phase 1: parallel content extraction."""
    async with AsyncAnthropic() as client:
        tasks = [extract_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]
```

---

## Resilience

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| tenacity | >=9.1,<10 | Retry with exponential backoff | PROJECT.md requires exponential backoff on all external API calls. Tenacity is the standard Python retry library. v9.1.4 current (Feb 2026). Supports async, custom wait strategies, jitter. |

**Confidence:** HIGH -- De facto standard, actively maintained, excellent async support.

### Retry Pattern

```python
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception_type
from anthropic import RateLimitError, APIConnectionError

@retry(
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
)
async def call_claude(prompt: str) -> str:
    ...
```

---

## Packaging / Tooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| uv | latest | Package management, venv, lockfiles | 10-100x faster than pip. Drop-in replacement. Handles venv creation, dependency resolution, and lockfile generation in one tool. The standard for new Python projects in 2026. |
| pyproject.toml | PEP 621 | Project metadata, dependencies | Modern Python packaging standard. Single source of truth for metadata, deps, tool config. |
| hatchling | >=1.25 | Build backend | Lightweight, fast build backend. Works with uv and pip. No setup.py needed. |
| ruff | >=0.15 | Linter + formatter | Replaces Black, Flake8, isort, pyupgrade in one tool. 150-200x faster than flake8. v0.15.2 current. |
| pytest | >=8.0 | Testing | Standard Python testing framework. |
| mypy | >=1.13 | Type checking | Static type analysis. All Pydantic models + Anthropic SDK are fully typed. |

**Confidence:** HIGH -- All are current community standards.

### pyproject.toml Structure

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "skill-builder"
version = "0.1.0"
description = "Multi-agent pipeline that builds Claude Code skills"
requires-python = ">=3.12"
license = "MIT"
dependencies = [
    "anthropic>=0.84,<1",
    "click>=8.3,<9",
    "pydantic>=2.12,<3",
    "langsmith>=0.7,<1",
    "openevals>=0.0.11",
    "exa-py>=2.7,<3",
    "tavily-python>=0.7,<1",
    "firecrawl-py>=4.14,<5",
    "tenacity>=9.1,<10",
    "httpx>=0.27",
]

[project.scripts]
skill-builder = "skill_builder.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.15",
    "mypy>=1.13",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CLI | Click | Typer | Typer wraps Click (extra layer), project scope is small, Click already specified in PROJECT.md |
| CLI | Click | argparse | Verbose, no ecosystem, manual everything |
| Data models | Pydantic v2 | dataclasses | No validation, no JSON schema generation, no model_json_schema() for tool_use |
| Data models | Pydantic v2 | attrs | Less ecosystem support, no native JSON schema, not used by Anthropic SDK |
| HTTP | httpx (transitive) | aiohttp | Adding second HTTP stack; httpx already in dependency tree via anthropic SDK |
| HTTP | httpx (transitive) | requests | No async support, would need aiohttp for async anyway |
| Retry | tenacity | stamina | stamina is simpler but less flexible; tenacity is the standard and handles async natively |
| Retry | tenacity | backoff | Less maintained than tenacity, smaller community |
| Tracing | LangSmith | Langfuse | PROJECT.md specifies LangSmith; it has native evaluate() and openevals integration |
| Tracing | LangSmith | Custom logging | Would duplicate what LangSmith does, more code to maintain |
| Packaging | uv | pip | pip is 10-100x slower, no lockfile, no venv management |
| Packaging | uv | Poetry | Poetry is heavier, slower, and uv handles everything Poetry does faster |
| Build backend | hatchling | setuptools | setuptools requires more config; hatchling is minimal and modern |
| Linting | ruff | Black + flake8 + isort | Three tools vs one; ruff is 150x faster |
| Agent framework | Direct Anthropic SDK | LangChain/LangGraph | Massive dependency bloat, unnecessary abstraction for a deterministic conductor with direct API calls |
| Agent framework | Direct Anthropic SDK | Pydantic AI | Adds another abstraction; this project's conductor is a state machine, not an LLM router |

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| LangChain | Enormous dependency tree, unnecessary abstraction layer. This project calls Anthropic directly with a deterministic state machine conductor. LangChain adds complexity without value here. |
| LangGraph | Same problem -- the conductor is a deterministic state machine, not an LLM-routed graph. State transitions are explicit Python code. |
| Pydantic AI | Adds an agent abstraction on top of the Anthropic SDK. The project's architecture (deterministic conductor + direct SDK calls) is simpler and more testable without it. |
| CrewAI / AutoGen | Multi-agent frameworks that assume LLM-driven orchestration. Antithetical to the deterministic conductor design. |
| OpenAI SDK | Not using OpenAI models. |
| Instructor | Was useful before Anthropic SDK had native structured outputs. Now redundant -- `tool_use` + `model_json_schema()` or `client.beta.messages.parse()` handles this natively. |
| aiohttp | Already getting httpx via Anthropic SDK. Two HTTP stacks is wasteful. |
| Poetry | uv is faster, simpler, and handles everything Poetry does. |
| Black / Flake8 / isort | ruff replaces all three in one faster tool. |

---

## Environment Variables Summary

```bash
# Required
ANTHROPIC_API_KEY=<anthropic-api-key>
EXA_API_KEY=<exa-api-key>
TAVILY_API_KEY=<tavily-api-key>
FIRECRAWL_API_KEY=<firecrawl-api-key>

# LangSmith (required for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<langsmith-api-key>
LANGCHAIN_PROJECT=skill-builder
```

---

## Installation

```bash
# With uv (recommended)
uv venv
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Dependency Graph (simplified)

```
skill-builder
  +-- click (CLI)
  +-- anthropic (Claude API)
  |     +-- httpx (HTTP, shared)
  |     +-- pydantic (models, shared)
  +-- pydantic (data models)
  +-- langsmith (tracing/eval)
  +-- openevals (LLM-as-judge evaluators)
  +-- exa-py (semantic search)
  +-- tavily-python (web search)
  +-- firecrawl-py (JS-rendered crawling)
  +-- tenacity (retry/backoff)
```

---

## Sources

- [Anthropic Python SDK - GitHub](https://github.com/anthropics/anthropic-sdk-python) -- HIGH confidence
- [Anthropic Python SDK - Releases](https://github.com/anthropics/anthropic-sdk-python/releases) -- v0.84.0, Feb 25, 2026
- [Anthropic Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- HIGH confidence
- [Anthropic Extended Thinking Docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) -- HIGH confidence
- [LangSmith Python SDK - PyPI](https://pypi.org/project/langsmith/) -- v0.7.9, MEDIUM confidence (fast-moving)
- [LangSmith Python SDK Reference](https://docs.smith.langchain.com/reference/python/reference) -- MEDIUM confidence
- [OpenEvals - GitHub](https://github.com/langchain-ai/openevals) -- MEDIUM confidence
- [Exa Python SDK - PyPI](https://pypi.org/project/exa-py/) -- v2.7.0, HIGH confidence
- [Exa Python SDK Spec](https://docs.exa.ai/sdks/python-sdk-specification) -- HIGH confidence
- [Tavily Python SDK - PyPI](https://pypi.org/project/tavily-python/) -- v0.7.22, HIGH confidence
- [Tavily SDK Reference](https://docs.tavily.com/sdk/python/reference) -- HIGH confidence
- [Firecrawl Python SDK - PyPI](https://pypi.org/project/firecrawl-py/) -- v4.18.0, HIGH confidence
- [Firecrawl Python SDK Docs](https://docs.firecrawl.dev/sdks/python) -- HIGH confidence
- [Click - PyPI](https://pypi.org/project/click/) -- v8.3.1, HIGH confidence
- [Pydantic - PyPI](https://pypi.org/project/pydantic/) -- v2.12.5, HIGH confidence
- [Tenacity - PyPI](https://pypi.org/project/tenacity/) -- v9.1.4, HIGH confidence
- [Ruff - PyPI](https://pypi.org/project/ruff/) -- v0.15.2, HIGH confidence
- [Python Packaging Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) -- HIGH confidence
- [uv vs pip - Real Python](https://realpython.com/uv-vs-pip/) -- HIGH confidence
