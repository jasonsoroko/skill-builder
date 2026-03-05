# Architecture Patterns

**Domain:** Multi-agent AI pipeline with deterministic conductor (skill-builder)
**Researched:** 2026-03-05

## Recommended Architecture

### High-Level Structure

```
CLI (Click)
  |
  v
Conductor (Deterministic State Machine)
  |
  |-- Phase 1: Harvest (parallel)
  |     |-- URL Classifier
  |     |-- Firecrawl Extractor
  |     |-- Exa Semantic Search
  |     |-- Tavily Web Search
  |     |-- Deduplicator
  |     '-- Saturation Checker (LLM)
  |
  |-- Phase 2: Synthesis (sequential)
  |     |-- Organizer Agent (Sonnet)
  |     |-- Gap Analyzer Agent (Opus)
  |     |     '-- [feedback loop -> Phase 1 if gaps found]
  |     |-- Learner Agent (Sonnet)
  |     |-- Mapper Agent (Sonnet)
  |     '-- Documenter Agent (Sonnet)
  |
  |-- Phase 3: Validation (sequential)
  |     |-- Heuristic Evaluators (compactness, syntax)
  |     |-- LLM-as-Judge Evaluators (Opus)
  |     |     '-- [feedback loop -> Phase 2 if score < 7]
  |     '-- Score Aggregator
  |
  '-- Phase 4: Packaging
        '-- .skill File Assembler

Checkpoint Store (JSON) <-- persisted at every phase boundary
LangSmith (@traceable)  <-- wraps every agent call
```

### The Conductor: A Deterministic State Machine, Not an LLM

The conductor is the single most important architectural decision. It is a plain Python state machine that manages phase transitions, checkpoint persistence, feedback loops, and error recovery. It never calls an LLM to decide "what to do next."

**Why deterministic:** LLM-routed orchestration adds latency (500ms-2s per routing decision), non-determinism (different routing on identical inputs), cost (extra tokens), and untestability (you cannot unit test probabilistic routing). A deterministic conductor is fast, free, predictable, and fully testable with standard pytest.

**Implementation:** Use a Python `Enum` for states with a hand-rolled state machine class. Do not adopt LangGraph or `python-statemachine` or `transitions` libraries. The conductor's logic is simple enough (6-8 states, 3-4 conditional transitions) that a library adds dependency weight without proportional value. A ~100-line class with an explicit transition table is clearer than a framework.

**Confidence:** HIGH -- this is well-established practice. Anthropic's own engineering blog advocates deterministic workflows over LLM routing for pipelines with known phase structures.

### State Machine Definition

```python
from enum import Enum

class PipelinePhase(Enum):
    INITIALIZED = "initialized"
    HARVESTING = "harvesting"
    ORGANIZING = "organizing"
    GAP_ANALYZING = "gap_analyzing"
    RE_HARVESTING = "re_harvesting"    # feedback loop
    LEARNING = "learning"
    MAPPING = "mapping"
    DOCUMENTING = "documenting"
    VALIDATING = "validating"
    RE_PRODUCING = "re_producing"      # feedback loop
    PACKAGING = "packaging"
    COMPLETE = "complete"
    FAILED = "failed"

# Transition table (deterministic, no LLM involved)
TRANSITIONS = {
    PipelinePhase.INITIALIZED:    PipelinePhase.HARVESTING,
    PipelinePhase.HARVESTING:     PipelinePhase.ORGANIZING,
    PipelinePhase.ORGANIZING:     PipelinePhase.GAP_ANALYZING,
    PipelinePhase.GAP_ANALYZING:  "conditional",  # -> LEARNING or RE_HARVESTING
    PipelinePhase.RE_HARVESTING:  PipelinePhase.ORGANIZING,
    PipelinePhase.LEARNING:       PipelinePhase.MAPPING,
    PipelinePhase.MAPPING:        PipelinePhase.DOCUMENTING,
    PipelinePhase.DOCUMENTING:    PipelinePhase.VALIDATING,
    PipelinePhase.VALIDATING:     "conditional",  # -> PACKAGING or RE_PRODUCING
    PipelinePhase.RE_PRODUCING:   PipelinePhase.VALIDATING,
    PipelinePhase.PACKAGING:      PipelinePhase.COMPLETE,
}
```

The two conditional transitions are resolved by examining structured data from the preceding agent (gap analysis results, validation scores), not by asking an LLM to route.

## Component Boundaries

| Component | Responsibility | Communicates With | I/O |
|-----------|---------------|-------------------|-----|
| **CLI** | Parse args, load skill brief, invoke conductor | Conductor | JSON brief in, .skill file out |
| **Conductor** | State transitions, checkpoint persistence, retry/feedback logic | All phases, Checkpoint Store | Phase results in/out, checkpoint reads/writes |
| **Checkpoint Store** | Persist/restore pipeline state as JSON | Conductor | JSON files on disk |
| **URL Classifier** | Classify URLs into extraction strategies | Harvest Executors | URL + metadata in, strategy enum out |
| **Harvest Executors** | Execute extraction (Firecrawl, Exa, Tavily) | URL Classifier, Deduplicator | URLs in, raw content out |
| **Deduplicator** | Remove duplicate content by URL + content hash | Harvest Executors, Saturation Checker | Content list in, deduplicated list out |
| **Saturation Checker** | LLM assessment of content completeness | Deduplicator, Conductor | Content + brief in, saturation report out |
| **Organizer Agent** | Categorize raw content into structured sections | Conductor | Raw content in, CategorizedResearch out |
| **Gap Analyzer Agent** | Cross-reference harvest against required_capabilities | Conductor | CategorizedResearch + brief in, GapReport out |
| **Learner Agent** | Extract KnowledgeModel from gap-free research | Conductor | CategorizedResearch in, KnowledgeModel out |
| **Mapper Agent** | Draft SKILL.md from KnowledgeModel | Conductor | KnowledgeModel in, SkillDraft out |
| **Documenter Agent** | Generate SETUP.md | Conductor | KnowledgeModel in, SetupDraft out |
| **Heuristic Evaluators** | Check compactness, syntax, format | Conductor | Drafts in, EvaluationResult out |
| **LLM-as-Judge Evaluators** | Assess API accuracy, completeness, trigger quality | Conductor | Drafts + brief in, EvaluationResult out |
| **Packager** | Assemble final .skill file | Conductor | Validated drafts in, .skill file out |

### Boundary Rules

1. **Agents never call other agents.** All routing goes through the conductor.
2. **Agents never read/write checkpoints.** Only the conductor persists state.
3. **Agents return Pydantic models.** Never raw strings. The conductor validates the shape.
4. **External API calls are wrapped in executor classes** with exponential backoff, not embedded in agents.

## Data Flow

### Primary Data Flow (happy path)

```
SkillBrief (JSON)
    |
    v
[URL Classifier] --> extraction strategies per URL
    |
    v
[Harvest Executors] --> parallel: Firecrawl, Exa, Tavily
    |                    asyncio.gather() with semaphore
    v
[Deduplicator] --> URL-keyed dict + SHA-256 content hash
    |
    v
[Saturation Checker] --> saturation report (pass/fail + missing areas)
    |
    v
RawHarvest (Pydantic model, persisted to checkpoint)
    |
    v
[Organizer Agent] --> CategorizedResearch
    |
    v
[Gap Analyzer Agent] --> GapReport (gaps: list[Gap], is_complete: bool)
    |
    |-- if gaps found: generate targeted queries, loop to Harvest
    |
    v
[Learner Agent] --> KnowledgeModel (structured extraction)
    |
    v
[Mapper Agent] --> SkillDraft (SKILL.md content)
    |
    v
[Documenter Agent] --> SetupDraft (SETUP.md content)
    |
    v
[Heuristic Evaluators] --> line count check, ast.parse code blocks
    |
    v
[LLM-as-Judge Evaluators] --> scored rubrics (1-10 per dimension)
    |
    |-- if any score < 7: route back to production with feedback
    |
    v
[Packager] --> .skill file on disk
```

### Feedback Loop Data Flow

There are exactly two feedback loops, both deterministic:

**Loop 1: Gap Analysis -> Re-Harvest**
```
GapReport.is_complete == False
  -> Conductor extracts GapReport.gaps[].suggested_queries
  -> Conductor sets phase = RE_HARVESTING
  -> Harvest runs only the targeted queries (not full re-crawl)
  -> Results merge into existing RawHarvest (deduplicated)
  -> Conductor increments gap_loop_count
  -> If gap_loop_count >= MAX_GAP_LOOPS (default 2): force proceed
  -> Re-enter Organizer -> Gap Analyzer
```

**Loop 2: Validation -> Re-Production**
```
Any EvaluationResult.score < 7
  -> Conductor collects all feedback strings from failed evaluators
  -> Conductor sets phase = RE_PRODUCING
  -> Mapper/Documenter re-invoked with original input + feedback
  -> Conductor increments validation_loop_count
  -> If validation_loop_count >= MAX_VALIDATION_LOOPS (default 2): force proceed with warning
  -> Re-enter Validation
```

Both loops have hard caps to prevent infinite cycling.

### State Shape (what the checkpoint persists)

```python
@dataclass
class PipelineState:
    phase: PipelinePhase
    skill_brief: SkillBrief
    raw_harvest: Optional[RawHarvest]
    categorized_research: Optional[CategorizedResearch]
    gap_report: Optional[GapReport]
    knowledge_model: Optional[KnowledgeModel]
    skill_draft: Optional[SkillDraft]
    setup_draft: Optional[SetupDraft]
    evaluation_results: list[EvaluationResult]
    gap_loop_count: int
    validation_loop_count: int
    error: Optional[str]
    started_at: datetime
    updated_at: datetime
```

This is serialized to JSON at every phase boundary. On resume, the conductor loads the checkpoint and re-enters at the persisted phase.

## Patterns to Follow

### Pattern 1: Base Agent Class with Forced Structured Output

**What:** Every agent inherits from a base class that wraps the Anthropic SDK, enforces structured output via `tool_use`, and applies `@traceable` for LangSmith observability.

**Why:** Eliminates boilerplate. Guarantees every agent call is traced, every output is validated, and the Anthropic SDK interaction pattern is consistent.

**Critical constraint:** When using adaptive thinking (extended thinking), you CANNOT use `tool_choice: {"type": "tool", "name": "..."}` to force a specific tool. Thinking requires `tool_choice: "auto"`. This means the base agent must handle the case where the model does not call the output tool on the first try.

**Implementation approach:**

```python
from anthropic import Anthropic
from langsmith import traceable
from pydantic import BaseModel

class BaseAgent:
    def __init__(self, model: str, system_prompt: str, output_model: type[BaseModel]):
        self.client = Anthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.output_schema = output_model.model_json_schema()
        self.output_model = output_model

    @traceable(run_type="llm")
    def run(self, input_data: BaseModel) -> BaseModel:
        tools = [{
            "name": "submit_output",
            "description": "Submit your structured output.",
            "input_schema": self.output_schema,
        }]

        response = self.client.messages.create(
            model=self.model,
            system=self.system_prompt,
            messages=[{"role": "user", "content": input_data.model_dump_json()}],
            tools=tools,
            tool_choice={"type": "auto"},  # MUST be auto for thinking
            max_tokens=16384,
            # thinking config added per-model
        )

        # Extract tool_use block, validate with Pydantic
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_output":
                return self.output_model.model_validate(block.input)

        raise AgentOutputError("Agent did not produce structured output")
```

**Confidence:** HIGH -- this pattern is directly from Anthropic's documentation and addresses the thinking + tool_choice constraint documented in their API.

### Pattern 2: URL Classification Strategy Pattern

**What:** Classify URLs by type before extraction, selecting the appropriate executor.

**Why:** Different URL types need different extraction strategies. A GitHub repo URL needs the GitHub API or raw file fetching. A docs site with JS rendering needs Firecrawl. An API schema endpoint needs direct HTTP + OpenAPI parsing.

```python
from enum import Enum

class URLType(Enum):
    GITHUB_REPO = "github_repo"
    DOCS_SITE = "docs_site"
    API_SCHEMA = "api_schema"
    BLOG_POST = "blog_post"
    UNKNOWN = "unknown"

class ExtractionStrategy(Enum):
    FIRECRAWL_CRAWL = "firecrawl_crawl"    # full site crawl with JS rendering
    FIRECRAWL_SCRAPE = "firecrawl_scrape"  # single page scrape
    DIRECT_FETCH = "direct_fetch"           # raw HTTP for schemas
    GITHUB_API = "github_api"               # GitHub contents API
    EXA_SEARCH = "exa_search"               # semantic discovery
    TAVILY_SEARCH = "tavily_search"         # web search

# Classification is deterministic (regex/heuristic), not LLM
def classify_url(url: str) -> URLType:
    if "github.com" in url and "/blob/" not in url:
        return URLType.GITHUB_REPO
    if any(url.endswith(ext) for ext in [".json", ".yaml", ".yml"]):
        return URLType.API_SCHEMA
    # ... etc

STRATEGY_MAP: dict[URLType, list[ExtractionStrategy]] = {
    URLType.GITHUB_REPO: [ExtractionStrategy.GITHUB_API],
    URLType.DOCS_SITE: [ExtractionStrategy.FIRECRAWL_CRAWL],
    URLType.API_SCHEMA: [ExtractionStrategy.DIRECT_FETCH],
    URLType.BLOG_POST: [ExtractionStrategy.FIRECRAWL_SCRAPE],
    URLType.UNKNOWN: [ExtractionStrategy.FIRECRAWL_SCRAPE],
}
```

**Confidence:** HIGH -- standard strategy pattern applied to a well-defined problem.

### Pattern 3: Checkpoint Persistence at Phase Boundaries

**What:** Serialize the full `PipelineState` to a JSON file after every phase completes. On CLI re-invocation, detect existing checkpoint and resume.

**Why:** LLM pipelines are expensive (time and cost). If the pipeline fails at Phase 3, the user should not re-run Phases 1-2. JSON is sufficient for local-only use -- no need for PostgreSQL or SQLite.

```python
import json
from pathlib import Path
from datetime import datetime

class CheckpointStore:
    def __init__(self, output_dir: Path):
        self.checkpoint_path = output_dir / "checkpoint.json"

    def save(self, state: PipelineState) -> None:
        state.updated_at = datetime.utcnow()
        self.checkpoint_path.write_text(
            json.dumps(state.to_dict(), indent=2, default=str)
        )

    def load(self) -> Optional[PipelineState]:
        if not self.checkpoint_path.exists():
            return None
        data = json.loads(self.checkpoint_path.read_text())
        return PipelineState.from_dict(data)

    def exists(self) -> bool:
        return self.checkpoint_path.exists()
```

**Confidence:** HIGH -- simple, appropriate for local-only tool.

### Pattern 4: Parallel Harvest with asyncio.gather + Semaphore

**What:** Run multiple extraction tasks concurrently in Phase 1 using asyncio, bounded by a semaphore to avoid overwhelming APIs.

**Why:** Harvest involves many independent I/O-bound operations (HTTP requests to Firecrawl, Exa, Tavily). Sequential execution wastes minutes of wall-clock time. A semaphore (e.g., 5 concurrent) prevents rate limiting.

```python
import asyncio

async def harvest_all(tasks: list[HarvestTask], max_concurrent: int = 5) -> list[HarvestResult]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_harvest(task: HarvestTask) -> HarvestResult:
        async with semaphore:
            return await execute_harvest(task)

    results = await asyncio.gather(
        *[bounded_harvest(t) for t in tasks],
        return_exceptions=True
    )
    # Handle exceptions individually, don't fail the whole batch
    return [r for r in results if not isinstance(r, Exception)]
```

**Confidence:** HIGH -- standard asyncio pattern.

### Pattern 5: LLM-as-Judge with Structured Rubrics

**What:** Validation evaluators return structured scores with justifications, not just pass/fail.

**Why:** The feedback loop needs specific, actionable critique to send back to production agents. "Score: 5" is useless. "Score: 5. The API examples use v2 endpoints but the current version is v3. Specifically, the /search endpoint changed from POST to GET in v3." gives the Mapper agent something to fix.

```python
class EvaluationDimension(BaseModel):
    dimension: str        # e.g., "api_accuracy", "completeness", "trigger_quality"
    score: int            # 1-10
    justification: str    # specific, actionable feedback
    evidence: list[str]   # quotes from the draft that support the score

class EvaluationResult(BaseModel):
    evaluator: str
    dimensions: list[EvaluationDimension]
    overall_pass: bool    # True if all dimensions >= 7
    feedback_for_revision: Optional[str]  # concatenated actionable feedback
```

**Confidence:** HIGH -- well-established LLM-as-judge pattern documented across multiple production systems.

## Anti-Patterns to Avoid

### Anti-Pattern 1: LLM-Routed Orchestration

**What:** Using an LLM to decide which phase to enter next.
**Why bad:** Adds 500ms-2s latency per transition, costs tokens, makes the pipeline non-deterministic, and is untestable. For a pipeline with known phases and structured transition conditions, this is pure overhead.
**Instead:** Deterministic conductor with enum states and a transition table.

### Anti-Pattern 2: Shared Mutable State Between Agents

**What:** Agents reading/writing to a shared dict or global state object.
**Why bad:** Creates hidden coupling, race conditions in parallel harvest, and makes it impossible to reason about data flow.
**Instead:** Each agent receives explicit input (Pydantic model) and returns explicit output (Pydantic model). The conductor is the only component that reads and writes the pipeline state.

### Anti-Pattern 3: Unbounded Feedback Loops

**What:** Letting gap analysis or validation loop indefinitely until "perfect."
**Why bad:** LLM evaluators can oscillate (score 6 -> fix -> score 6 on different dimension). Without a hard cap, the pipeline runs forever.
**Instead:** `MAX_GAP_LOOPS = 2`, `MAX_VALIDATION_LOOPS = 2`. Force-proceed with a logged warning.

### Anti-Pattern 4: Framework-Heavy Orchestration (LangGraph, CrewAI)

**What:** Adopting LangGraph or CrewAI for the conductor layer.
**Why bad for this project:** These frameworks solve the general case (arbitrary graphs, dynamic routing, multi-turn agent conversations). This project has a fixed, linear pipeline with two conditional branches. The frameworks add dependency weight, learning curve, and abstraction overhead for a problem that needs ~100 lines of hand-rolled state machine.
**Instead:** Hand-rolled conductor class with Python Enum states.

**Caveat:** LangGraph would be appropriate if the pipeline needed dynamic task decomposition, multi-turn agent dialogues, or user-defined graph structures. It does not.

### Anti-Pattern 5: Forcing Tool Choice with Adaptive Thinking

**What:** Using `tool_choice: {"type": "tool", "name": "submit_output"}` while adaptive thinking is enabled.
**Why bad:** The Anthropic API rejects this combination with an error. This is a hard API constraint, not a soft recommendation.
**Instead:** Use `tool_choice: {"type": "auto"}` and handle the case where the model responds with text instead of a tool call (retry with a follow-up message asking it to use the tool).

## Directory Structure

```
skill-builder/
  pyproject.toml
  src/
    skill_builder/
      __init__.py
      cli.py                    # Click CLI entry point
      conductor.py              # Deterministic state machine
      checkpoint.py             # JSON checkpoint store
      models/
        __init__.py
        brief.py                # SkillBrief input model
        harvest.py              # RawHarvest, HarvestResult
        synthesis.py            # CategorizedResearch, GapReport, KnowledgeModel
        production.py           # SkillDraft, SetupDraft
        evaluation.py           # EvaluationResult, EvaluationDimension
        state.py                # PipelineState
      agents/
        __init__.py
        base.py                 # BaseAgent with @traceable + tool_use
        organizer.py            # Organizer (Sonnet)
        gap_analyzer.py         # Gap Analyzer (Opus)
        learner.py              # Learner (Sonnet)
        mapper.py               # Mapper (Sonnet)
        documenter.py           # Documenter (Sonnet)
        saturation.py           # Saturation Checker (Sonnet)
      evaluators/
        __init__.py
        base.py                 # BaseEvaluator
        heuristic.py            # Compactness, syntax evaluators
        llm_judge.py            # LLM-as-judge evaluators (Opus)
      harvest/
        __init__.py
        classifier.py           # URL classification
        executors.py            # Firecrawl, Exa, Tavily executors
        dedup.py                # Deduplication logic
      packaging/
        __init__.py
        assembler.py            # .skill file assembly
  tests/
    ...
```

## Suggested Build Order (Dependencies Between Components)

Build order is dictated by dependency chains. You cannot test higher layers without lower layers existing.

### Layer 0: Foundation (no dependencies)
1. **models/** -- All Pydantic models. Everything else depends on these.
2. **checkpoint.py** -- JSON persistence. Conductor depends on it.
3. **agents/base.py** -- BaseAgent class. All agents depend on it.

### Layer 1: Core Infrastructure
4. **conductor.py** -- State machine. Depends on models + checkpoint.
5. **cli.py** -- Click entry point. Depends on conductor.
6. **harvest/classifier.py** -- URL classification. Depends on models.

### Layer 2: Harvest Phase
7. **harvest/executors.py** -- Firecrawl, Exa, Tavily wrappers. Depends on models.
8. **harvest/dedup.py** -- Deduplication. Depends on models.
9. **agents/saturation.py** -- Saturation checker. Depends on base agent + models.

### Layer 3: Synthesis Phase
10. **agents/organizer.py** -- Depends on base agent + synthesis models.
11. **agents/gap_analyzer.py** -- Depends on base agent + synthesis models.
12. **agents/learner.py** -- Depends on base agent + synthesis models.

### Layer 4: Production Phase
13. **agents/mapper.py** -- Depends on base agent + production models.
14. **agents/documenter.py** -- Depends on base agent + production models.

### Layer 5: Validation Phase
15. **evaluators/heuristic.py** -- Depends on evaluation models.
16. **evaluators/llm_judge.py** -- Depends on base agent + evaluation models.

### Layer 6: Packaging
17. **packaging/assembler.py** -- Depends on production models.

### Layer 7: Integration
18. Wire conductor to all phases (harvest -> synthesis -> validation -> packaging).
19. End-to-end testing with a real skill brief.

**Implication for roadmap:** Layers 0-1 form the first milestone. Each subsequent layer is a milestone. Feedback loops (gap analysis, validation) should be added after their constituent phases work independently.

## Scalability Considerations

| Concern | Current (local Mac) | If Scaled Later |
|---------|---------------------|-----------------|
| Concurrency | asyncio semaphore (5 concurrent) | Would need task queue (Celery/dramatiq) |
| Checkpoint storage | JSON files | SQLite or PostgreSQL |
| Observability | LangSmith traces | Same (LangSmith scales) |
| Cost tracking | LangSmith dashboard | Same |
| Multiple simultaneous runs | One at a time (CLI) | Would need run isolation (run IDs, separate dirs) |

For the current scope (local Mac, single user, CLI), the simple approaches are correct. Do not over-engineer for scale that is not needed.

## Sources

- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) -- MEDIUM confidence (could not fetch full content, used search summaries)
- [Anthropic: Building with extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) -- HIGH confidence (official docs)
- [Anthropic: Implement tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use) -- HIGH confidence (official docs)
- [Anthropic: Structured outputs from agents](https://platform.claude.com/docs/en/agent-sdk/structured-outputs) -- HIGH confidence (official docs)
- [Anthropic: Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) -- MEDIUM confidence
- [pytransitions/transitions](https://github.com/pytransitions/transitions) -- HIGH confidence (GitHub repo)
- [python-statemachine](https://python-statemachine.readthedocs.io/) -- HIGH confidence (official docs)
- [LangSmith: DynamicRunEvaluator](https://docs.smith.langchain.com/reference/python/evaluation/langsmith.evaluation.evaluator.DynamicRunEvaluator) -- HIGH confidence (official docs)
- [LangSmith @traceable](https://docs.langchain.com/langsmith/trace-with-langchain) -- HIGH confidence (official docs)
- [Firecrawl quickstart](https://docs.firecrawl.dev/introduction) -- HIGH confidence (official docs)
- [AWS: Evaluator reflect-refine loop patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/evaluator-reflect-refine-loop-patterns.html) -- MEDIUM confidence
- [Deterministic AI Architecture (Kubiya)](https://www.kubiya.ai/blog/deterministic-ai-architecture) -- LOW confidence (vendor blog)
- [OpenClaw deterministic multi-agent pipeline](https://dev.to/ggondim/how-i-built-a-deterministic-multi-agent-dev-pipeline-inside-openclaw-and-contributed-a-missing-4ool) -- MEDIUM confidence
