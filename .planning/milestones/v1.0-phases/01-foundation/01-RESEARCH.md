# Phase 1: Foundation - Research

**Researched:** 2026-03-05
**Domain:** Python CLI scaffold, deterministic state machine, checkpoint persistence, LangSmith tracing, resilience patterns
**Confidence:** HIGH

## Summary

Phase 1 builds the backbone of skill-builder: the conductor state machine that drives runs through all pipeline phases (intake through packaging) with stub agents, the Pydantic data models that define every inter-agent boundary, JSON checkpoint persistence for resume capability, the Click CLI entry point, LangSmith tracing integration, and resilience patterns (exponential backoff, budget cap). No real agents are built -- all phase-specific agents are stubs returning fixture data.

The technology stack is mature and well-verified. Click 8.3, Pydantic v2, the Anthropic SDK v0.84.0, LangSmith's `wrap_anthropic` + `@traceable`, and tenacity are all current, well-documented, and compatible. The critical model IDs have been resolved: `claude-sonnet-4-6` (alias) and `claude-opus-4-6` (alias) -- no date-stamped IDs needed for the alias form. Token pricing is confirmed: Sonnet 4.6 at $3/$15 per MTok (input/output), Opus 4.6 at $5/$25 per MTok.

The primary risk for Phase 1 is the state machine design: every state must have both success and failure transitions, feedback loops must have hard caps, and the FAILED state must be reachable from every non-terminal state. Secondary risks are LangSmith crash-through (tracing errors must never kill the pipeline) and the OBS-03 requirement conflict (REQUIREMENTS.md says "no local tracking" but user explicitly decided on local budget enforcement -- user decision wins).

**Primary recommendation:** Build models first, then checkpoint store, then conductor state machine, then CLI, then tracing wrapper, then resilience patterns. Each layer depends on the one before it. Stub agents are thin wrappers that return hardcoded Pydantic models.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- URLs are typed by source: `{"url": "...", "type": "docs|github|api_schema|blog"}`. Content router still validates at harvest time but gets a hint.
- Strict validation with good errors: required fields fail fast with specific messages, optional fields get sensible defaults with a note about what was defaulted.
- `required_capabilities` are free-text strings: `["authentication", "batch operations"]`. Gap Analyzer interprets them semantically.
- Ship an `examples/exa-tavily-firecrawl.json` as the first target skill brief. Doubles as documentation and smoke test.
- Single command: `skill-builder build brief.json [--dry-run] [--resume] [--verbose] [--budget N] [--force]`. One thing the tool does.
- Normal output: phase banners + status lines. Print phase transitions with timing: `[harvest] Starting... [harvest] Complete (12s, 8 pages)`.
- `--verbose` adds agent-level detail: which agent is running, what it received/returned (truncated), per-agent timing.
- `--dry-run` outputs a fetch plan table + cost estimate: URLs to crawl, searches to run, agents to invoke, estimated token usage and dollar cost per phase.
- State files live in `.skill-builder/state/` in CWD (colocated with where you run the tool). Gitignore it.
- Resume shows a one-line summary: "Resuming 'exa-tavily-firecrawl' from [synthesis] (harvest complete, 14 pages extracted). Continuing..."
- `--resume` is explicit -- user must pass the flag. Without it, a fresh run starts.
- If state exists and user runs without `--resume` or `--force`: warn and exit. "State exists for 'exa-tavily-firecrawl'. Use --resume to continue or --force to start fresh."
- Default global budget: $25 (overridable via `--budget`). Covers typical runs with feedback loops.
- When exceeded: finish current agent (don't waste in-flight work), then halt with clear message showing spend vs budget. State is checkpointed so user can resume with higher budget.
- Tracked via local token counter from Anthropic API response `usage` fields. LangSmith is for observability/reporting only -- budget enforcement is real-time and local.
- Budget covers Anthropic tokens only. External API costs (Exa, Tavily, Firecrawl) are excluded -- they're pay-per-call with known fixed costs.

### Claude's Discretion
- Exact Pydantic model field names and nesting
- State machine implementation pattern (enum-based, class-based, etc.)
- LangSmith @traceable wrapper implementation details
- Tenacity retry configuration specifics (initial wait, max wait, jitter)
- Logging framework choice (stdlib logging, loguru, structlog)
- Internal error handling patterns

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-01 | User can provide a structured skill brief (JSON) with seed URLs, tool category, scope, required capabilities, and deploy target | Pydantic v2 BaseModel with strict validation; typed URLs with `type` field per user decision; `model_json_schema()` for schema export; `model_validate_json()` for loading from file |
| CORE-02 | Conductor implements a deterministic state machine with explicit phase transitions (intake -> harvest -> synthesis -> production -> validation -> packaging) | Python Enum states with transition table dict; hand-rolled ~100-line class; no library needed for 6-8 states with 2 conditional branches |
| CORE-03 | Conductor routes Gap Analyzer failures back to harvest with recommended search queries (max 2 iterations) | Conditional transition from GAP_ANALYZING state; conductor reads GapReport.is_sufficient; gap_loop_count field in PipelineState; hard cap at 2 |
| CORE-04 | Conductor routes validation failures back to production with evaluator feedback (max 2 iterations) | Conditional transition from VALIDATING state; conductor reads EvaluationResult.overall_pass; validation_loop_count in PipelineState; hard cap at 2 |
| CORE-05 | Pipeline state persists to JSON at every phase boundary in `.skill-builder/state/{tool_name}.json` | Pydantic `model_dump_json()` for serialization, `model_validate_json()` for deserialization; CheckpointStore class writes to `.skill-builder/state/` per user decision |
| CORE-06 | Pipeline can resume from any checkpoint after failure | CheckpointStore.load() returns PipelineState; conductor re-enters at persisted phase; `--resume` flag triggers load; state clash without `--resume`/`--force` warns and exits |
| CORE-07 | Dry-run mode prints fetch plan and estimated API cost, then exits | Conductor walks state machine with stub agents to build plan; cost estimates from verified pricing: Sonnet 4.6 $3/$15 MTok, Opus 4.6 $5/$25 MTok; prints table and exits |
| CORE-08 | Global token budget cap prevents runaway costs in feedback loops | Local TokenBudget class tracks cumulative tokens from `response.usage.input_tokens` + `output_tokens`; converts to cost using per-model pricing; $25 default; finish current agent then halt |
| CORE-09 | CLI entry point via Click accepts brief file path and options (dry-run, resume, verbose) | Click `@click.command()` with `@click.argument('brief')` and `@click.option()` decorators; entry point in pyproject.toml `[project.scripts]` |
| OBS-01 | All Anthropic API calls are wrapped with LangSmith `@traceable` decorator | LangSmith `wrap_anthropic()` patches the Anthropic client to auto-trace all calls; `@traceable` on conductor and agent functions for full span tree |
| OBS-02 | Each agent run includes metadata tags for phase, agent name, and iteration number | `@traceable(tags=["phase:harvest"], metadata={"agent": "organizer", "iteration": 1})` or dynamic via `langsmith_extra` kwarg at call time |
| OBS-03 | Cost and token tracking is fully offloaded to LangSmith (no local tracking) | **CONFLICT: User explicitly decided on local token tracking for budget enforcement.** LangSmith handles observability/reporting; local counter handles real-time budget enforcement. OBS-03 as written is overridden by user decision. |
| RES-01 | Exponential backoff on all external API calls (Anthropic, Exa, Tavily, Firecrawl) | Tenacity `@retry` with `wait=wait_exponential_jitter(initial=1, max=60, jitter=5)`, `stop=stop_after_attempt(5)`, `retry=retry_if_exception_type(...)` |
| RES-02 | LangSmith tracing errors never block the pipeline (wrapped at integration boundary) | try/except around all LangSmith interactions; test with `LANGSMITH_TRACING=false` to verify independence; `wrap_anthropic` itself is resilient but verify |
| RES-03 | Feedback loops have hard iteration caps (max 2 for gap analysis, max 2 for validation) | `MAX_GAP_LOOPS = 2` and `MAX_VALIDATION_LOOPS = 2` as conductor constants; force-proceed with warning after cap |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | >=3.12, <3.15 | Runtime | 3.12 floor for Pydantic v2 perf, f-string improvements, improved error messages |
| Click | >=8.3, <9 | CLI framework | Single command with options; explicit decorator API; specified in PROJECT.md |
| Pydantic | >=2.12, <3 | Data models, validation, serialization | All agent I/O, checkpoint persistence, brief schema; v2 Rust core is 5-50x faster than v1 |
| anthropic | >=0.84, <1 | Claude API client | Official SDK; `response.usage` fields for local token tracking; `tool_use` for structured output |
| langsmith | >=0.7, <1 | Tracing, observability | `wrap_anthropic()` for auto-tracing; `@traceable` for span tree; env-var controlled |
| tenacity | >=9.1, <10 | Retry with exponential backoff | De facto standard; async-native; `wait_exponential_jitter` for API resilience |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | (transitive via anthropic) | HTTP client | Direct HTTP calls (e.g., fetching OpenAPI specs); already in dep tree |
| pytest | >=8.0 | Testing | All unit and integration tests |
| ruff | >=0.15 | Linter + formatter | Replaces Black + Flake8 + isort; 150x faster |
| mypy | >=1.13 | Type checking | All Pydantic models + SDK are fully typed |
| hatchling | >=1.25 | Build backend | Lightweight, works with uv |
| uv | latest | Package management | 10-100x faster than pip; handles venv + lockfile |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Click | Typer | Typer wraps Click; adds indirection for small CLI surface |
| Hand-rolled state machine | python-statemachine / transitions | Library adds dependency for ~100 lines of code; overkill for 6-8 states |
| stdlib logging | structlog / loguru | Discretion area; structlog adds structured JSON logging; loguru simplifies config |
| JSON checkpoints | SQLite | Overkill for local single-user CLI; JSON is simpler, human-readable |

**Installation:**
```bash
uv venv
uv pip install -e ".[dev]"
```

## Architecture Patterns

### Recommended Project Structure
```
skill-builder/
  pyproject.toml
  examples/
    exa-tavily-firecrawl.json          # First target skill brief (user decision)
  src/
    skill_builder/
      __init__.py
      cli.py                            # Click CLI entry point
      conductor.py                      # Deterministic state machine
      checkpoint.py                     # JSON checkpoint store
      budget.py                         # Local token budget tracker
      tracing.py                        # LangSmith wrapper (resilient)
      models/
        __init__.py
        brief.py                        # SkillBrief input model (typed URLs)
        state.py                        # PipelineState, PipelinePhase enum
        harvest.py                      # RawHarvest, HarvestResult
        synthesis.py                    # CategorizedResearch, GapReport, KnowledgeModel
        production.py                   # SkillDraft, SetupDraft
        evaluation.py                   # EvaluationResult, EvaluationDimension
      agents/
        __init__.py
        base.py                         # BaseAgent with tracing + tool_use
        stubs.py                        # Stub agents for Phase 1 (return fixtures)
      resilience.py                     # Tenacity retry decorators
  tests/
    __init__.py
    conftest.py                         # Shared fixtures
    test_models.py                      # Pydantic model validation
    test_conductor.py                   # State machine transitions
    test_checkpoint.py                  # Persistence round-trip
    test_budget.py                      # Token budget tracking
    test_cli.py                         # CLI invocation via Click testing
    test_tracing.py                     # LangSmith wrapper resilience
```

### Pattern 1: Pydantic-Based State Machine with Enum Phases
**What:** The conductor uses a `PipelinePhase` Enum for states and a `PipelineState` Pydantic BaseModel for all persistent data. The transition table is a simple dict mapping current phase to next phase (or "conditional" for feedback loops).
**When to use:** Always -- this is the core pattern for the entire project.
**Example:**
```python
# Source: Architecture research + Anthropic engineering blog patterns
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

class PipelinePhase(str, Enum):
    """Use str mixin for JSON-serializable enum values."""
    INITIALIZED = "initialized"
    INTAKE = "intake"
    HARVESTING = "harvesting"
    ORGANIZING = "organizing"
    GAP_ANALYZING = "gap_analyzing"
    RE_HARVESTING = "re_harvesting"
    LEARNING = "learning"
    MAPPING = "mapping"
    DOCUMENTING = "documenting"
    VALIDATING = "validating"
    RE_PRODUCING = "re_producing"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    FAILED = "failed"

class PipelineState(BaseModel):
    """Full pipeline state -- serialized to JSON at phase boundaries."""
    phase: PipelinePhase = PipelinePhase.INITIALIZED
    brief_name: str
    # Phase outputs stored as Optional -- populated as pipeline progresses
    raw_harvest: dict | None = None       # Placeholder; real model in Phase 2
    categorized_research: dict | None = None
    gap_report: dict | None = None
    knowledge_model: dict | None = None
    skill_draft: dict | None = None
    setup_draft: dict | None = None
    evaluation_results: list[dict] = Field(default_factory=list)
    # Loop counters
    gap_loop_count: int = 0
    validation_loop_count: int = 0
    # Budget tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    # Metadata
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Serialization: model_dump_json() / model_validate_json()
state = PipelineState(brief_name="exa-tavily-firecrawl")
json_str = state.model_dump_json(indent=2)
restored = PipelineState.model_validate_json(json_str)
```

### Pattern 2: Resilient LangSmith Tracing Wrapper
**What:** All LangSmith integration goes through a single module that catches and suppresses tracing errors. The `wrap_anthropic` function patches the Anthropic client for auto-tracing; `@traceable` decorates conductor and agent functions.
**When to use:** Every Anthropic API call and every significant function in the pipeline.
**Example:**
```python
# Source: LangSmith docs (https://docs.langchain.com/langsmith/trace-anthropic)
import logging
from anthropic import Anthropic
from langsmith.wrappers import wrap_anthropic
from langsmith import traceable

logger = logging.getLogger(__name__)

def create_traced_client() -> Anthropic:
    """Create Anthropic client with LangSmith tracing.

    Falls back to untraced client if LangSmith is unavailable.
    """
    client = Anthropic()
    try:
        client = wrap_anthropic(client)
    except Exception:
        logger.warning("LangSmith tracing unavailable; running without tracing")
    return client

# Use @traceable on conductor/agent functions
@traceable(
    name="conductor_run_phase",
    run_type="chain",
    tags=["conductor"],
)
def run_phase(state: PipelineState, phase: str) -> PipelineState:
    # Dynamic metadata via langsmith_extra at call site
    ...
```

### Pattern 3: Local Token Budget Tracker
**What:** A `TokenBudget` class reads `response.usage.input_tokens` and `response.usage.output_tokens` after every Anthropic API call, accumulates totals, and converts to USD using per-model pricing. The conductor checks the budget after each agent call and halts if exceeded.
**When to use:** After every Anthropic API call in the pipeline.
**Example:**
```python
# Source: Anthropic pricing docs (https://platform.claude.com/docs/en/about-claude/pricing)
from dataclasses import dataclass

# Verified pricing per million tokens (2026-03-05)
MODEL_PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

@dataclass
class TokenBudget:
    budget_usd: float = 25.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from response.usage and update cost."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-6"])
        cost = (input_tokens / 1_000_000 * pricing["input"]
                + output_tokens / 1_000_000 * pricing["output"])
        self.total_cost_usd += cost

    @property
    def exceeded(self) -> bool:
        return self.total_cost_usd >= self.budget_usd

    @property
    def remaining_usd(self) -> float:
        return max(0, self.budget_usd - self.total_cost_usd)
```

### Pattern 4: Click CLI with State Clash Detection
**What:** Single `build` command with argument and options. On invocation: load brief, check for existing state, enforce `--resume`/`--force` semantics, then invoke conductor.
**When to use:** The CLI entry point.
**Example:**
```python
# Source: Click docs (https://click.palletsprojects.com/en/stable/)
import click
from pathlib import Path

@click.command()
@click.argument("brief", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Show fetch plan and cost estimate, then exit")
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.option("--verbose", is_flag=True, help="Show agent-level detail")
@click.option("--budget", type=float, default=25.0, help="Global token budget in USD")
@click.option("--force", is_flag=True, help="Overwrite existing state")
def build(brief: Path, dry_run: bool, resume: bool, verbose: bool, budget: float, force: bool):
    """Build a Claude Code skill from a skill brief."""
    # 1. Load and validate brief
    # 2. Check state clash
    # 3. Create/resume conductor
    # 4. Run (or dry-run)
    ...

def main():
    build()
```

### Pattern 5: Tenacity Retry Decorator Factory
**What:** A shared retry decorator for all external API calls. Uses exponential backoff with jitter. Retries on specific exception types only.
**When to use:** Wrap every external API call (Anthropic, Exa, Tavily, Firecrawl).
**Example:**
```python
# Source: Tenacity docs (https://tenacity.readthedocs.io/)
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception_type
from anthropic import RateLimitError, APIConnectionError, APIStatusError

def api_retry(max_attempts: int = 5):
    """Retry decorator for external API calls with exponential backoff + jitter."""
    return retry(
        wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
        stop=stop_after_attempt(max_attempts),
        retry=retry_if_exception_type((
            RateLimitError,
            APIConnectionError,
            # Retry on 5xx server errors only
        )),
        reraise=True,
    )
```

### Anti-Patterns to Avoid
- **LLM-routed orchestration:** Never use an LLM to decide which phase comes next. The transition table is a Python dict.
- **Shared mutable state between agents:** Each agent receives input and returns output. Only the conductor reads/writes PipelineState.
- **Unbounded feedback loops:** Always enforce `MAX_GAP_LOOPS = 2` and `MAX_VALIDATION_LOOPS = 2`. Force-proceed with warning.
- **Indexing response.content[0]:** Always iterate and filter by `block.type == "tool_use"`. The response can contain text, thinking, and tool_use blocks in any order.
- **Forcing tool_choice with thinking enabled:** When extended thinking is active, `tool_choice` must be `"auto"`. Cannot force a specific tool name. (Affects Phase 2+ but base agent must handle this from the start.)
- **Letting LangSmith errors crash the pipeline:** All tracing is wrapped in try/except at the integration boundary.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff | Custom retry loops | tenacity `@retry` with `wait_exponential_jitter` | Edge cases: jitter, max wait, exception filtering, async support |
| CLI argument parsing | argparse boilerplate | Click `@click.command` + `@click.option` | Type conversion, help generation, testing utilities |
| JSON schema generation | Manual schema dicts | Pydantic `model_json_schema()` | Always in sync with model definition; handles nested models |
| JSON serialization of models | `json.dumps` + custom encoders | Pydantic `model_dump_json()` / `model_validate_json()` | Handles datetime, enums, nested models, Optional fields correctly |
| Anthropic API tracing | Manual logging of API calls | LangSmith `wrap_anthropic()` | Auto-captures input/output tokens, model, messages, tool calls |
| HTTP client | requests or aiohttp | httpx (transitive via anthropic) | Already in dependency tree; sync + async in one library |

**Key insight:** Phase 1 has zero novel libraries to integrate. Every component uses well-established Python patterns. The complexity is in the wiring (state machine transitions, checkpoint persistence, budget tracking), not in the individual pieces.

## Common Pitfalls

### Pitfall 1: State Machine Missing Terminal States
**What goes wrong:** Some code paths never reach COMPLETE or FAILED. Example: evaluator scores below 7, routes to re-production, which again scores below 7 -- infinite loop.
**Why it happens:** State machines are designed for the happy path first. Error states are afterthoughts.
**How to avoid:** Every non-terminal state must have both a success transition and a failure/cap-exceeded transition. Both feedback loops have hard caps (2 iterations). After cap: force-proceed with warning, not loop forever. Draw the state diagram and verify every state has outgoing edges.
**Warning signs:** Any run exceeding 15 minutes. Any state visited more than 3 times.

### Pitfall 2: LangSmith @traceable Crashing the Pipeline
**What goes wrong:** `@traceable` encounters a network error or missing API key and the exception propagates, crashing the pipeline.
**Why it happens:** Default behavior of `@traceable` can allow exceptions to bubble up if misconfigured. LangSmith SDK has had issues with this (langsmith-sdk issue #1306).
**How to avoid:** Wrap `wrap_anthropic()` in try/except. Test pipeline with `LANGSMITH_TRACING=false` to verify independence. Never let observability errors block business logic.
**Warning signs:** Unhandled exceptions from `langsmith` or `langchain_core` packages.

### Pitfall 3: Pydantic v2 Optional Field Semantics
**What goes wrong:** Using `Optional[str]` thinking it means "field can be omitted." In Pydantic v2, `Optional[str]` means "required but nullable." The field must be present in JSON with value `null`.
**Why it happens:** Pydantic v2 changed semantics from v1. Most Python devs expect v1 behavior.
**How to avoid:** Use `str | None = None` for truly optional fields with a default. This means "can be omitted from JSON, defaults to None." Test every model's JSON schema with `model_json_schema()` to verify field requirements.
**Warning signs:** `ValidationError: field required` when deserializing checkpoints with missing optional fields.

### Pitfall 4: Checkpoint Serialization of Datetime and Enum
**What goes wrong:** Using `json.dumps()` instead of Pydantic's `model_dump_json()` for checkpoint serialization. `datetime` and `Enum` objects cause `TypeError: Object of type X is not JSON serializable`.
**Why it happens:** Habit of using `json.dumps` from non-Pydantic projects.
**How to avoid:** Always use `model_dump_json()` for writing and `model_validate_json()` for reading. Pydantic handles datetime ISO formatting and enum value serialization automatically. Use `str` mixin on enums (`class PipelinePhase(str, Enum)`) for clean JSON output.
**Warning signs:** `TypeError` during checkpoint writes.

### Pitfall 5: Click Entry Point Configuration
**What goes wrong:** Using `[tool.setuptools.entry_points]` instead of `[project.scripts]` in pyproject.toml. Or forgetting to install the package (`uv pip install -e .`) before testing the CLI command.
**Why it happens:** Multiple legacy formats exist for declaring CLI entry points.
**How to avoid:** Use `[project.scripts]` (PEP 621 standard): `skill-builder = "skill_builder.cli:main"`. Install with `uv pip install -e ".[dev]"` and test the `skill-builder` command immediately.
**Warning signs:** `command not found: skill-builder` after installation.

### Pitfall 6: OBS-03 Requirement Conflict
**What goes wrong:** Implementing OBS-03 as written ("Cost and token tracking is fully offloaded to LangSmith -- no local tracking") contradicts the user's explicit decision to track tokens locally for real-time budget enforcement.
**Why it happens:** REQUIREMENTS.md was written before the user's implementation decisions in CONTEXT.md.
**How to avoid:** Follow the user's CONTEXT.md decision: local token counter from `response.usage` fields for budget enforcement, LangSmith for observability/reporting. OBS-03 is satisfied by LangSmith tracking cost data for dashboard reporting; the "no local tracking" clause is overridden.
**Warning signs:** Implementing budget enforcement via LangSmith API calls (adds latency, couples to external service).

## Code Examples

### Anthropic API Response Usage Extraction
```python
# Source: Anthropic SDK types (https://github.com/anthropics/anthropic-sdk-python)
# response.usage fields after every messages.create() call:
#   response.usage.input_tokens: int
#   response.usage.output_tokens: int
#   response.usage.cache_creation_input_tokens: int (if caching)
#   response.usage.cache_read_input_tokens: int (if caching)

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    messages=[{"role": "user", "content": "..."}],
)

# Extract usage for budget tracking
budget.record_usage(
    model="claude-sonnet-4-6",
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
)
```

### Tool Use Response Handling (Correct Pattern)
```python
# Source: Anthropic tool_use docs + pitfalls research
# NEVER index response.content[0] -- always filter by type
def extract_tool_result(response, tool_name: str, output_model: type[BaseModel]) -> BaseModel:
    """Extract and validate a tool_use result from an Anthropic response."""
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return output_model.model_validate(block.input)
    raise ValueError(
        f"No tool_use block for '{tool_name}' in response. "
        f"stop_reason={response.stop_reason}, "
        f"content_types={[b.type for b in response.content]}"
    )
```

### Stop Reasons Reference
```python
# Source: Anthropic API docs (https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)
# stop_reason values:
#   "end_turn"     -- model naturally completed
#   "tool_use"     -- model wants to call a tool
#   "max_tokens"   -- hit max_tokens limit
#   "stop_sequence" -- matched a stop sequence
#   "pause_turn"   -- model paused (continue conversation)
#   "refusal"      -- safety refusal
```

### Checkpoint Store with Pydantic
```python
# Source: Pydantic docs (https://docs.pydantic.dev/latest/concepts/serialization/)
from pathlib import Path

class CheckpointStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, brief_name: str) -> Path:
        return self.state_dir / f"{brief_name}.json"

    def save(self, state: PipelineState) -> None:
        state.updated_at = datetime.utcnow()
        self._path(state.brief_name).write_text(state.model_dump_json(indent=2))

    def load(self, brief_name: str) -> PipelineState | None:
        path = self._path(brief_name)
        if not path.exists():
            return None
        return PipelineState.model_validate_json(path.read_text())

    def exists(self, brief_name: str) -> bool:
        return self._path(brief_name).exists()
```

### Phase Banner Output Style
```python
# Source: User decision -- "feel clean and informative, think uv or ruff output style"
import time

def phase_banner(phase: str, status: str = "Starting") -> None:
    """Print a clean phase banner."""
    print(f"  [{phase}] {status}")

def phase_complete(phase: str, elapsed: float, detail: str = "") -> None:
    """Print phase completion with timing."""
    suffix = f", {detail}" if detail else ""
    print(f"  [{phase}] Complete ({elapsed:.1f}s{suffix})")

# Usage:
# phase_banner("harvest")
# ...
# phase_complete("harvest", 12.3, "8 pages")
# Output:
#   [harvest] Starting
#   [harvest] Complete (12.3s, 8 pages)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain/LangGraph for orchestration | Direct Anthropic SDK + hand-rolled conductor | 2024-2025 industry shift | Simpler, fewer deps, more predictable |
| Pydantic v1 `Optional[str]` = optional field | Pydantic v2 `str \| None = None` for optional | Pydantic v2 (June 2023) | Must use v2 pattern or fields become required |
| `json.dumps()` + custom encoders | Pydantic `model_dump_json()` | Pydantic v2 | Handles all types; faster (Rust core) |
| Instructor library for structured output | Native `tool_use` + `model_json_schema()` | Anthropic SDK 2024 | No extra dependency needed |
| `LANGCHAIN_API_KEY` env var | `LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY` (both work) | LangSmith SDK 0.7+ | Either env var name works |
| pip for package management | uv | 2024-2025 | 10-100x faster; handles venv + lockfile |

**Deprecated/outdated:**
- `response.content[0]` indexing for tool_use results -- content blocks can be in any order with thinking enabled
- `tool_choice: {"type": "tool", "name": "..."}` with extended thinking -- must use `"auto"` when thinking is enabled
- `Anthropic.parse()` / `client.beta.messages.parse()` -- the structured-outputs beta works but `tool_use` + `model_json_schema()` is the more established path
- `LANGCHAIN_TRACING_V2` env var name -- still works but `LANGSMITH_TRACING` is the newer canonical name

## Model IDs and Pricing Reference

Verified from official Anthropic documentation (2026-03-05):

| Model | API ID (alias) | Input Price | Output Price | Max Output | Context |
|-------|---------------|-------------|--------------|------------|---------|
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | $3 / MTok | $15 / MTok | 64K tokens | 200K (1M beta) |
| Claude Opus 4.6 | `claude-opus-4-6` | $5 / MTok | $25 / MTok | 128K tokens | 200K (1M beta) |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1 / MTok | $5 / MTok | 64K tokens | 200K |

Tool use system prompt overhead: 346 tokens (auto/none) or 313 tokens (any/tool) for all 4.x models.

## Open Questions

1. **Logging framework choice (Claude's discretion)**
   - What we know: stdlib `logging` is the safe default. `structlog` adds structured JSON output. `loguru` simplifies configuration.
   - What's unclear: Whether the verbose output pattern (phase banners) should use logging or direct print().
   - Recommendation: Use stdlib `logging` for internal operations (DEBUG/INFO/WARNING). Use direct `print()` / `click.echo()` for user-facing output (phase banners, status lines, dry-run tables). This separates concerns: logging is for developers, print is for users.

2. **Async vs sync for Phase 1**
   - What we know: Phase 1 has no parallel operations (stub agents are instant). Phase 2 harvest needs async for parallel URL fetching.
   - What's unclear: Whether to build the conductor as async from the start or add async later.
   - Recommendation: Build the conductor as sync for Phase 1. Stub agents are synchronous. Add async to the harvest layer in Phase 2 using `asyncio.run()` at the conductor boundary. This avoids premature async complexity.

3. **Stub agent return data**
   - What we know: Stub agents must return valid Pydantic models that the conductor can serialize to checkpoints.
   - What's unclear: How much fixture data is needed to exercise all state machine paths.
   - Recommendation: Create minimal fixture data that exercises: (a) happy path through all phases, (b) gap analysis failure triggering re-harvest, (c) validation failure triggering re-production, (d) budget exceeded halt. Four fixture sets total.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` (Wave 0 -- create in first task) |
| Quick run command | `pytest tests/ -x --timeout=10` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | Skill brief JSON loads and validates correctly | unit | `pytest tests/test_models.py::test_skill_brief_valid -x` | Wave 0 |
| CORE-01 | Invalid brief fails with specific error messages | unit | `pytest tests/test_models.py::test_skill_brief_invalid -x` | Wave 0 |
| CORE-02 | Conductor transitions through all phases with stubs | unit | `pytest tests/test_conductor.py::test_happy_path -x` | Wave 0 |
| CORE-03 | Gap analysis failure routes to re-harvest (max 2) | unit | `pytest tests/test_conductor.py::test_gap_loop -x` | Wave 0 |
| CORE-04 | Validation failure routes to re-production (max 2) | unit | `pytest tests/test_conductor.py::test_validation_loop -x` | Wave 0 |
| CORE-05 | State persists to JSON at phase boundaries | unit | `pytest tests/test_checkpoint.py::test_save_load_roundtrip -x` | Wave 0 |
| CORE-06 | Pipeline resumes from checkpoint | integration | `pytest tests/test_conductor.py::test_resume_from_checkpoint -x` | Wave 0 |
| CORE-07 | Dry-run prints plan and exits | integration | `pytest tests/test_cli.py::test_dry_run -x` | Wave 0 |
| CORE-08 | Budget exceeded halts after current agent | unit | `pytest tests/test_budget.py::test_budget_exceeded -x` | Wave 0 |
| CORE-09 | CLI accepts brief and all options | unit | `pytest tests/test_cli.py::test_cli_options -x` | Wave 0 |
| OBS-01 | Anthropic calls are traceable (mock) | unit | `pytest tests/test_tracing.py::test_wrap_anthropic -x` | Wave 0 |
| OBS-02 | Traces include phase/agent/iteration metadata | unit | `pytest tests/test_tracing.py::test_metadata_tags -x` | Wave 0 |
| RES-01 | Retry fires on simulated failures | unit | `pytest tests/test_resilience.py::test_exponential_backoff -x` | Wave 0 |
| RES-02 | LangSmith failure does not crash pipeline | unit | `pytest tests/test_tracing.py::test_tracing_failure_resilience -x` | Wave 0 |
| RES-03 | Feedback loops respect hard caps | unit | `pytest tests/test_conductor.py::test_loop_caps -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --timeout=10`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pyproject.toml` -- project metadata, dependencies, pytest config, ruff config, entry point
- [ ] `tests/conftest.py` -- shared fixtures (sample brief, mock anthropic client, tmp state dir)
- [ ] `tests/test_models.py` -- covers CORE-01
- [ ] `tests/test_conductor.py` -- covers CORE-02, CORE-03, CORE-04, CORE-06, RES-03
- [ ] `tests/test_checkpoint.py` -- covers CORE-05
- [ ] `tests/test_budget.py` -- covers CORE-08
- [ ] `tests/test_cli.py` -- covers CORE-07, CORE-09
- [ ] `tests/test_tracing.py` -- covers OBS-01, OBS-02, RES-02
- [ ] `tests/test_resilience.py` -- covers RES-01
- [ ] Framework install: `uv pip install -e ".[dev]"` -- pytest, ruff, mypy

## Sources

### Primary (HIGH confidence)
- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) -- model IDs, context windows, max output, pricing
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) -- per-token costs for Sonnet 4.6 and Opus 4.6, usage object structure, tool use token overhead
- [Anthropic Handling Stop Reasons](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons) -- stop_reason enum values
- [Anthropic SDK Python (GitHub)](https://github.com/anthropics/anthropic-sdk-python) -- Message.usage fields, response structure
- [LangSmith Trace Anthropic](https://docs.langchain.com/langsmith/trace-anthropic) -- wrap_anthropic usage, @traceable integration
- [LangSmith Add Metadata and Tags](https://docs.langchain.com/langsmith/add-metadata-tags) -- static and dynamic tag/metadata patterns
- [Click Documentation 8.3.x](https://click.palletsprojects.com/en/stable/) -- command/option/argument decorators
- [Pydantic Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) -- model_dump_json, model_validate_json
- [Tenacity Documentation](https://tenacity.readthedocs.io/) -- retry, wait_exponential_jitter, async support

### Secondary (MEDIUM confidence)
- [LangSmith Tracing Deep Dive](https://medium.com/@aviadr1/langsmith-tracing-deep-dive-beyond-the-docs-75016c91f747) -- practical patterns beyond official docs
- [LangSmith @traceable Crash Issue (GitHub #1306)](https://github.com/langchain-ai/langsmith-sdk/issues/1306) -- tracing error propagation bug
- [LangSmith wrap_anthropic reference](https://reference.langchain.com/python/langsmith/observability/sdk/wrappers/) -- function signature

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions verified via official docs and PyPI; model IDs confirmed
- Architecture: HIGH -- patterns from existing project research are well-aligned with verified SDK APIs
- Pitfalls: HIGH -- critical pitfalls (state machine gaps, LangSmith crash-through, Pydantic v2 semantics) confirmed via official docs and GitHub issues
- Token pricing: HIGH -- verified directly from Anthropic pricing page (2026-03-05)
- Model IDs: HIGH -- `claude-sonnet-4-6` and `claude-opus-4-6` confirmed as API aliases on models overview page

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain; 30-day window appropriate)

---
*Phase: 01-foundation*
*Research completed: 2026-03-05*
