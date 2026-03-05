# Phase 3: Output Pipeline - Research

**Researched:** 2026-03-05
**Domain:** Production agents, LLM-as-judge validation, skill packaging, Rich CLI progress
**Confidence:** HIGH

## Summary

Phase 3 replaces four stub agents (Mapper, Documenter, Validator, Packager) with real implementations and adds Rich CLI progress output across the entire pipeline. The phase spans three distinct domains: (1) production agents that draft SKILL.md and SETUP.md from a KnowledgeModel, (2) validation evaluators (2 heuristic + 3 LLM-as-judge) with feedback routing, and (3) packaging the final .skill file for different deploy targets. Rich is a new dependency that must be added.

The codebase is well-structured for this work. Stub agents define exact I/O shapes (SkillDraft, SetupDraft, EvaluationResult, dict), the conductor already handles production-validation-packaging transitions with feedback loops, and Phase 2 established patterns for Anthropic SDK usage (messages.parse, output_format, system prompts as module constants, asyncio.to_thread bridging). The primary complexity is in the ValidatorAgent which must orchestrate 5 evaluators with fail-fast logic and parallel LLM calls.

**Primary recommendation:** Build in three plans: (1) production agents (Mapper + Documenter) and heuristic evaluators, (2) LLM-as-judge evaluators and ValidatorAgent with conductor wiring, (3) Packager agent and Rich CLI integration.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Worked examples must be complete runnable snippets: imports, setup, execution, output handling. Copy-pasteable.
- Include an explicit DO/DON'T section derived from gotchas and anti-patterns in the KnowledgeModel.
- Single ValidatorAgent runs all 5 evaluators internally and returns a unified EvaluationResult.
- Heuristic evaluators (compactness, syntax) run first and fail-fast: if either fails, skip the 3 expensive Opus LLM-as-judge calls.
- Syntax evaluator validates Python code blocks only (via ast.parse). Skip bash, JSON, YAML, and other language blocks.
- The 3 LLM-as-judge evaluators (API accuracy, completeness, trigger quality) run in parallel via asyncio.gather.
- When validation fails and routes back to production, pass only the failed dimensions with their feedback strings.
- Output folder structure: SKILL.md and SETUP.md at root, with references/, scripts/, and assets/ subdirectories. LICENSE.txt (MIT) at root.
- Deploy targets differ by output path: repo -> .claude/skills/{tool_name}/, user -> ~/.claude/skills/{tool_name}/, package -> .skill-builder/output/{tool_name}/
- After packaging, print manual verification steps.
- Use Rich Live display with a status panel: current phase, active agent, iteration count, elapsed time.
- Auto-detect non-TTY and degrade to plain text log lines.
- --verbose adds budget summary at phase boundaries.
- Final run summary panel after packaging: total time, total cost, evaluator scores, feedback loop counts, output path, verification instructions.
- Evaluator scores display as 9/10 PASS or 4/10 FAIL.

### Claude's Discretion
- Mapper's approach to SKILL.md section ordering and structure
- Mapper's reference extraction strategy (what goes to references/ vs stays inline)
- Trigger description wording and aggressiveness
- Documenter's SETUP.md structure and troubleshooting tip selection
- Rich panel layout and styling details
- How the ValidatorAgent passes organized research to the API accuracy evaluator
- How to bridge sync/async for parallel LLM evaluator calls within ValidatorAgent

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROD-01 | Mapper agent (Sonnet) translates KnowledgeModel into draft SKILL.md under 500 lines | Sonnet messages.parse pattern from Phase 2 agents; Claude Code skill format researched |
| PROD-02 | SKILL.md includes YAML frontmatter with specific, pushy trigger description | Skill authoring docs: description must be third-person, specific, include key terms |
| PROD-03 | SKILL.md includes worked examples for all canonical use cases | KnowledgeModel.canonical_use_cases provides input; examples must be copy-pasteable |
| PROD-04 | Large reference sections extracted to references/ directory | Skill best practices: keep SKILL.md < 500 lines, use progressive disclosure |
| PROD-05 | Documenter agent (Sonnet) writes SETUP.md with prerequisites, API keys, quick start, troubleshooting | Same Sonnet messages.parse pattern; SetupDraft model already exists |
| VAL-01 | Compactness evaluator checks SKILL.md is under 500 lines | Pure Python: content.count('\n') + 1 <= 500 |
| VAL-02 | Syntax evaluator extracts Python code blocks and runs ast.parse | ast.parse for syntax validation; regex to extract ```python blocks |
| VAL-03 | API Accuracy evaluator (Opus, LLM-as-judge) verifies endpoints, classes, CLI flags | Opus messages.parse with EvaluationDimension output; needs organized research as context |
| VAL-04 | Completeness evaluator (Opus, LLM-as-judge) verifies all use cases have examples | Same Opus LLM-as-judge pattern; needs KnowledgeModel as context |
| VAL-05 | Trigger Quality evaluator (Opus, LLM-as-judge) verifies trigger description quality | Same pattern; needs KnowledgeModel.trigger_phrases as reference |
| VAL-06 | Any score below 7 triggers feedback routing to production | EvaluationDimension.passed = score >= 7; conductor already handles routing |
| PKG-01 | Packager assembles output folder: SKILL.md, references/, scripts/, assets/, LICENSE.txt | Pure Python Path operations; mkdir, write_text |
| PKG-02 | Packager produces .skill file based on deploy_target | Path resolution per deploy target; copy assembled folder to target path |
| PKG-03 | Pipeline prints installation verification instructions after packaging | click.echo or Rich console.print with specific trigger question examples |
| CORE-10 | Rich CLI progress shows current phase, agent activity, completion status | Rich Live display, Panel, Table; new dependency rich>=14.0 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.84,<1 | Already installed; Sonnet for production agents, Opus for LLM-as-judge | Project standard; messages.parse with output_format for Pydantic enforcement |
| rich | >=14.0,<15 | CLI progress display, panels, tables, live status | De facto Python terminal UI library; handles TTY detection automatically |
| pydantic | >=2.12,<3 | Already installed; models for agent I/O | Project standard; used for all agent output schemas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ast (stdlib) | N/A | Python syntax validation in code blocks | Syntax evaluator: ast.parse each extracted Python block |
| re (stdlib) | N/A | Extract code blocks from markdown | Regex to find ```python...``` blocks in SKILL.md |
| asyncio (stdlib) | N/A | Parallel LLM evaluator execution | asyncio.gather for 3 independent Opus calls |
| shutil (stdlib) | N/A | Copy assembled folder to deploy target | Packager: shutil.copytree for final deployment |
| pathlib (stdlib) | N/A | Path resolution for deploy targets | Packager: Path.home() / ".claude/skills/..." |
| textwrap (stdlib) | N/A | License text formatting | MIT LICENSE.txt generation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Rich | Click.echo (existing) | Click.echo can't do live updating panels; Rich handles TTY fallback |
| ast.parse | exec/compile | ast.parse is safer -- no execution, just syntax tree parsing |
| asyncio.gather | concurrent.futures | asyncio.gather is simpler for I/O-bound parallel; consistent with Phase 2 pattern |

**Installation:**
```bash
uv add "rich>=14.0,<15"
```

## Architecture Patterns

### Recommended Module Structure
```
src/skill_builder/
├── agents/
│   ├── mapper.py           # MapperAgent: KnowledgeModel -> SkillDraft
│   ├── documenter.py       # DocumenterAgent: KnowledgeModel -> SetupDraft
│   ├── validator.py        # ValidatorAgent: orchestrates 5 evaluators
│   └── packager.py         # PackagerAgent: assembles + deploys
├── evaluators/
│   ├── __init__.py
│   ├── compactness.py      # Heuristic: line count check
│   ├── syntax.py           # Heuristic: ast.parse Python blocks
│   ├── api_accuracy.py     # LLM-as-judge: Opus
│   ├── completeness.py     # LLM-as-judge: Opus
│   └── trigger_quality.py  # LLM-as-judge: Opus
├── progress.py             # Rich CLI progress display
└── ...existing files...
```

### Pattern 1: Production Agent (Mapper/Documenter)
**What:** Same pattern as Phase 2 agents (OrganizerAgent, LearnerAgent). Sonnet with messages.parse and output_format for Pydantic-enforced output.
**When to use:** For Mapper and Documenter agents that generate structured content.
**Example:**
```python
# Source: Existing Phase 2 pattern (organizer.py, learner.py)
class MapperAgent:
    """Translates KnowledgeModel into a draft SKILL.md.

    Conforms to BaseAgent Protocol: run(**kwargs) -> SkillDraft.
    """

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or create_traced_client()

    def run(self, **kwargs: Any) -> SkillDraft:
        knowledge_model: dict = kwargs["knowledge_model"]
        brief: SkillBrief = kwargs["brief"]
        # Optional: evaluation feedback for re-production
        failed_dimensions: list[dict] | None = kwargs.get("failed_dimensions")

        km = KnowledgeModel.model_validate(knowledge_model)
        prompt = self._build_prompt(km, brief, failed_dimensions)

        response = self.client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            output_format=SkillDraft,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.parsed_output
```

### Pattern 2: Heuristic Evaluator
**What:** Pure Python function that returns an EvaluationDimension. No LLM calls.
**When to use:** For compactness and syntax checks.
**Example:**
```python
# Heuristic evaluator pattern
def check_compactness(skill_content: str) -> EvaluationDimension:
    """Check SKILL.md is under 500 lines."""
    line_count = skill_content.count("\n") + 1
    passed = line_count <= 500
    return EvaluationDimension(
        name="compactness",
        score=10 if passed else max(1, 10 - (line_count - 500) // 50),
        feedback=f"{line_count} lines" + ("" if passed else f" (exceeds 500-line limit by {line_count - 500})"),
        passed=passed,
    )

def check_syntax(skill_content: str) -> EvaluationDimension:
    """Extract Python code blocks and validate syntax via ast.parse."""
    import ast
    import re

    # Match ```python ... ``` blocks
    pattern = r"```python\s*\n(.*?)```"
    blocks = re.findall(pattern, skill_content, re.DOTALL)

    errors = []
    for i, block in enumerate(blocks, 1):
        try:
            ast.parse(block)
        except SyntaxError as e:
            errors.append(f"Block {i}: {e.msg} (line {e.lineno})")

    passed = len(errors) == 0
    if not blocks:
        feedback = "No Python code blocks found"
    elif passed:
        feedback = f"All {len(blocks)} Python blocks valid"
    else:
        feedback = "; ".join(errors)

    return EvaluationDimension(
        name="syntax",
        score=10 if passed else max(1, 10 - len(errors) * 2),
        feedback=feedback,
        passed=passed,
    )
```

### Pattern 3: LLM-as-Judge Evaluator
**What:** Opus with messages.parse returning a structured score + feedback. Each evaluator is an async function for parallel execution.
**When to use:** For API accuracy, completeness, and trigger quality checks.
**Example:**
```python
# LLM-as-judge evaluator pattern
async def evaluate_api_accuracy(
    client: Anthropic,
    skill_content: str,
    organized_research: dict,
) -> EvaluationDimension:
    """Verify API names, endpoints, and flags against organized research."""

    prompt = f"""Score this skill's API accuracy from 1-10.

SKILL.md content:
{skill_content}

Organized research (ground truth):
{json.dumps(organized_research, indent=2)}

Check every endpoint, class name, method name, and CLI flag in the skill.
Score 10 = all correct; 7+ = minor issues only; <7 = significant errors.
Provide specific feedback about any inaccuracies found."""

    # Use asyncio.to_thread to wrap sync Anthropic call
    response = await asyncio.to_thread(
        client.messages.parse,
        model="claude-opus-4-6",
        max_tokens=4096,
        output_format=EvaluationDimension,
        system="You are an API accuracy evaluator. Score strictly based on evidence in the research.",
        messages=[{"role": "user", "content": prompt}],
    )
    dim = response.parsed_output
    # Override name to ensure consistency
    return EvaluationDimension(
        name="api_accuracy",
        score=dim.score,
        feedback=dim.feedback,
        passed=dim.score >= 7,
    )
```

### Pattern 4: ValidatorAgent Orchestration
**What:** Single agent that runs heuristics first (fail-fast), then LLM evaluators in parallel, returns unified EvaluationResult.
**When to use:** The ValidatorAgent.
**Example:**
```python
class ValidatorAgent:
    def run(self, **kwargs: Any) -> EvaluationResult:
        # ... extract kwargs ...

        # Phase 1: Heuristics (fail-fast)
        compactness = check_compactness(skill_content)
        syntax = check_syntax(skill_content)
        dimensions = [compactness, syntax]

        if not compactness.passed or not syntax.passed:
            return EvaluationResult(
                dimensions=dimensions,
                overall_pass=False,
                iteration=iteration,
            )

        # Phase 2: LLM evaluators in parallel
        # Bridge sync->async using ThreadPoolExecutor pattern from HarvestAgent
        llm_dims = self._run_llm_evaluators(skill_content, ...)
        dimensions.extend(llm_dims)

        overall = all(d.passed for d in dimensions)
        return EvaluationResult(dimensions=dimensions, overall_pass=overall, iteration=iteration)

    def _run_llm_evaluators(self, ...) -> list[EvaluationDimension]:
        """Run 3 LLM evaluators in parallel via asyncio."""
        async def _parallel():
            return await asyncio.gather(
                evaluate_api_accuracy(self.client, ...),
                evaluate_completeness(self.client, ...),
                evaluate_trigger_quality(self.client, ...),
            )

        # Same sync-to-async bridge as HarvestAgent
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _parallel())
                return future.result()
        else:
            return asyncio.run(_parallel())
```

### Pattern 5: Rich CLI Progress Integration
**What:** Rich Live display wrapping the conductor run, updating a status panel as phases progress.
**When to use:** Replace print() calls in conductor with Rich-powered progress.
**Example:**
```python
# progress.py -- Rich CLI progress display
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

class PipelineProgress:
    """Rich CLI progress display for the pipeline.

    Auto-detects TTY and degrades to plain text when piped.
    """

    def __init__(self, verbose: bool = False) -> None:
        self.console = Console()
        self.verbose = verbose
        self._is_tty = self.console.is_terminal
        self._start_time: float | None = None
        self._phase: str = ""
        self._agent: str = ""
        self._iteration: int = 0

    def phase_start(self, phase: str, agent: str) -> None:
        if self._is_tty:
            # Update live display
            ...
        else:
            self.console.print(f"[{phase}] Starting {agent}...")

    def phase_complete(self, phase: str, elapsed: float) -> None:
        if self._is_tty:
            ...
        else:
            self.console.print(f"[{phase}] Complete ({elapsed:.1f}s)")

    def eval_score(self, name: str, score: int, passed: bool) -> None:
        status = "PASS" if passed else "FAIL"
        color = "green" if passed else "red"
        self.console.print(f"  {name}: [{color}]{score}/10 {status}[/]")

    def summary_panel(self, ...) -> None:
        """Final run summary panel."""
        table = Table(show_header=False, box=None)
        table.add_row("Total time:", f"{elapsed:.1f}s")
        table.add_row("Total cost:", f"${cost:.4f}")
        ...
        self.console.print(Panel(table, title="Build Complete"))
```

### Pattern 6: Deploy Target Path Resolution
**What:** Resolve the output path based on the brief's deploy_target field.
**When to use:** PackagerAgent final step.
**Example:**
```python
def resolve_deploy_path(deploy_target: str, tool_name: str) -> Path:
    """Resolve output path based on deploy target."""
    if deploy_target == "repo":
        return Path(".claude/skills") / tool_name
    elif deploy_target == "user":
        return Path.home() / ".claude" / "skills" / tool_name
    elif deploy_target == "package":
        return Path(".skill-builder/output") / tool_name
    else:
        raise ValueError(f"Unknown deploy target: {deploy_target}")
```

### Anti-Patterns to Avoid
- **Running LLM evaluators sequentially:** The 3 Opus calls are independent and should always run via asyncio.gather for ~3x speedup.
- **Running Opus evaluators on obvious failures:** The heuristic fail-fast is a cost optimization. A 600-line SKILL.md will obviously need re-production; no point scoring its API accuracy.
- **Passing ALL evaluator feedback on re-production:** Only failed dimensions should be sent back. Passing scores for passing dimensions creates noise and wastes tokens.
- **Using response.stop_reason without checking:** If max_tokens truncates an LLM evaluator, the parsed output may be incomplete. Check stop_reason == "max_tokens" and handle (already done in gap_analyzer.py).
- **Building the Rich Live display around individual agents:** The progress display should wrap the conductor.run() loop, not be embedded inside each agent.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal UI with live updates | Custom ANSI escape codes | Rich Live + Panel + Table | Handles terminal detection, encoding, resize, clearing |
| Python syntax validation | Custom parser | ast.parse (stdlib) | Standard library, handles all Python syntax including f-strings, walrus operator |
| Code block extraction from markdown | Manual string splitting | Regex `r"```python\s*\n(.*?)```"` with re.DOTALL | Clean, handles multiline, avoids edge cases with manual parsing |
| MIT license text | Write from scratch | Constant string with year/author interpolation | Standard template, no variations needed |
| Path resolution with home dir | Manual env var parsing | pathlib.Path.home() | Cross-platform, handles ~, avoids $HOME parsing |

**Key insight:** This phase's complexity is in prompt engineering (system prompts for production agents and evaluators) and orchestration (fail-fast + parallel). The actual I/O shapes, transition logic, and data flow are already handled by the existing conductor and models.

## Common Pitfalls

### Pitfall 1: SkillDraft Content Exceeding 500 Lines
**What goes wrong:** The Mapper generates SKILL.md content over 500 lines, which then fails the compactness evaluator and triggers an unnecessary feedback loop.
**Why it happens:** Without explicit guidance in the system prompt, LLMs tend to be verbose. The KnowledgeModel may contain extensive data that the Mapper tries to include inline.
**How to avoid:** The Mapper's system prompt must emphasize the 500-line budget explicitly. Instruct the Mapper to extract large sections (API reference tables, extensive examples) to references/ files proactively. Include line count awareness in the prompt.
**Warning signs:** SkillDraft.line_count consistently above 450 on first pass.

### Pitfall 2: ast.parse False Positives on Incomplete Code Snippets
**What goes wrong:** Code blocks in SKILL.md may be intentionally incomplete (showing a function body without the function def, or using `...` as placeholder), and ast.parse rejects them.
**Why it happens:** ast.parse expects complete, valid Python. Skill examples often show fragments.
**How to avoid:** Wrap each code block in a try/except SyntaxError. Consider wrapping fragments in a function body before parsing. If the code block contains `...` or obvious placeholders, skip it or be lenient in scoring.
**Warning signs:** Syntax evaluator fails on code blocks that are intentionally pedagogical.

### Pitfall 3: LLM Evaluator Score Inconsistency
**What goes wrong:** The same SKILL.md gets different scores on re-evaluation, causing non-deterministic pass/fail decisions.
**Why it happens:** LLM-as-judge is inherently stochastic. Without a clear rubric, scores drift.
**How to avoid:** Provide detailed scoring rubrics in the evaluator system prompts. Be explicit about what 1-3, 4-6, 7-8, 9-10 mean for each dimension. Use temperature=0 if the SDK supports it (it does not with messages.parse -- but adaptive thinking helps anchor reasoning).
**Warning signs:** The same skill draft passes on one run and fails on another without content changes.

### Pitfall 4: Feedback Loop Infinite Quality Chasing
**What goes wrong:** The Mapper fixes one issue but introduces another, causing oscillating pass/fail.
**Why it happens:** The re-production prompt isn't specific enough, or fixing one dimension degrades another.
**How to avoid:** The max 2 iterations cap (already enforced by conductor) prevents infinite loops. When passing failed dimensions back, be very specific about what to fix and what to preserve.
**Warning signs:** Validation loop count always reaching the cap (2).

### Pitfall 5: Rich Live Display Conflicts with Agent Logging
**What goes wrong:** Agent log messages (logger.info) and Rich Live updates interfere, producing garbled terminal output.
**Why it happens:** Rich Live redirects stdout/stderr by default. If agents write directly to stdout (via print()), it conflicts.
**How to avoid:** Use Rich's console.print() for all output, or use live.console.print() to print above the live display. Replace conductor's existing print() calls with the progress display API. Ensure logging goes to stderr or is captured by Rich.
**Warning signs:** Garbled output during pipeline runs with Rich enabled.

### Pitfall 6: Deploy Target Path Permissions
**What goes wrong:** Writing to ~/.claude/skills/ fails because the directory doesn't exist, or the user doesn't have write permissions.
**Why it happens:** The target directory may not have been created yet. User-scope skills are a newer feature.
**How to avoid:** Use Path.mkdir(parents=True, exist_ok=True) before writing. Catch PermissionError and provide a helpful message suggesting the user create the directory manually or use a different deploy target.
**Warning signs:** FileNotFoundError or PermissionError on packaging.

### Pitfall 7: Conductor _build_kwargs Not Passing Evaluation Feedback
**What goes wrong:** When validation fails and RE_PRODUCING runs the Mapper again, the Mapper doesn't receive the evaluator feedback, so it can't fix the specific issues.
**Why it happens:** The current _build_kwargs for RE_PRODUCING only passes knowledge_model and brief. The CONTEXT.md requires passing failed dimensions with feedback.
**How to avoid:** Update _build_kwargs for RE_PRODUCING to also pass the failed evaluation dimensions. Store them on state (or extract from the last evaluation_results entry).
**Warning signs:** Re-production generates essentially the same output as the first attempt.

## Code Examples

### Extracting Python Code Blocks from Markdown
```python
# Source: Python stdlib re + ast modules
import re
import ast

def extract_python_blocks(markdown: str) -> list[str]:
    """Extract Python code blocks from markdown content."""
    pattern = r"```python\s*\n(.*?)```"
    return re.findall(pattern, markdown, re.DOTALL)

def validate_python_block(code: str) -> tuple[bool, str]:
    """Validate a Python code block via ast.parse.

    Returns (is_valid, error_message).
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"{e.msg} (line {e.lineno})"
```

### YAML Frontmatter Structure for Generated SKILL.md
```yaml
# Source: https://code.claude.com/docs/en/skills, https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
---
name: exa-tavily-firecrawl
description: Performs deep research crawling using Exa semantic search, Tavily web search, and Firecrawl site crawling. Use when researching a topic that requires crawling documentation sites, searching for examples and best practices, or gathering comprehensive information from multiple sources.
---
```
Key rules for the description field:
- Third person only ("Performs..." not "I can..." or "You can...")
- Must include both what the skill does AND when to use it
- Maximum 1024 characters
- Be specific and include key terms/trigger words
- Name field: lowercase letters, numbers, hyphens only, max 64 chars

### Rich Live Display with Status Panel
```python
# Source: https://rich.readthedocs.io/en/latest/live.html
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()

def build_status_table(phase: str, agent: str, iteration: int, elapsed: float) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("label", style="dim")
    table.add_column("value", style="bold")
    table.add_row("Phase:", phase)
    table.add_row("Agent:", agent)
    table.add_row("Iteration:", str(iteration))
    table.add_row("Elapsed:", f"{elapsed:.1f}s")
    return table

# Non-TTY fallback: Rich's Console auto-detects is_terminal
# When not a terminal, Panel/Table render without ANSI codes
```

### Budget Summary Display (--verbose)
```python
# Source: CONTEXT.md specific formatting
def format_budget(spent: float, budget: float) -> str:
    pct = (spent / budget * 100) if budget > 0 else 0
    return f"${spent:.2f} / ${budget:.2f} ({pct:.1f}%)"

# Example output: $5.82 / $25.00 (23.3%)
```

### MIT License Template
```python
# Standard MIT license text
MIT_LICENSE = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rich 13.x | Rich 14.x (14.2.0 current) | Jul 2025 | Nested Live display support; no breaking changes for our use case |
| Anthropic SDK tool_choice for structured output | messages.parse with output_format | Late 2025 | Simpler API; automatic Pydantic validation; already used in Phase 2 |
| Skills as .claude/commands/ | Skills as .claude/skills/ with SKILL.md + frontmatter | 2025 | Full folder structure, frontmatter metadata, progressive disclosure |
| Simple skill descriptions | Pushy trigger descriptions with specific terms + when-to-use guidance | 2025 | Discovery driven by description quality; third-person required |

**Deprecated/outdated:**
- `.claude/commands/` still works but `.claude/skills/` is the recommended path with more features
- `tool_choice` for structured output works but `messages.parse` with `output_format` is the newer, simpler approach (already used in this project)

## Open Questions

1. **EvaluationDimension Model for LLM-as-Judge**
   - What we know: The EvaluationDimension model has name, score, feedback, passed fields. LLM evaluators need to return this structure.
   - What's unclear: Should the LLM be asked to set `passed` (derived from score >= 7) or should we always override it programmatically after getting the score?
   - Recommendation: Always override `passed = score >= 7` programmatically after LLM returns score. Don't trust the LLM to apply the threshold consistently.

2. **RE_PRODUCING Kwargs Update**
   - What we know: Current _build_kwargs for RE_PRODUCING passes only knowledge_model and brief. The CONTEXT.md requires passing failed evaluation feedback.
   - What's unclear: Whether to add a new state field for failed_dimensions or extract from evaluation_results[-1].
   - Recommendation: Extract from `state.evaluation_results[-1]` at dispatch time in _build_kwargs. Filter to only dimensions where `passed=False`. No new state field needed.

3. **Mapper's Reference Extraction Decision**
   - What we know: SKILL.md must be < 500 lines. Large sections should go to references/.
   - What's unclear: Should the Mapper output include both the SKILL.md content and the reference file contents in a single response? Or should reference extraction be a post-processing step?
   - Recommendation: Extend SkillDraft model to include an optional `reference_files: dict[str, str]` field (filename -> content). The Mapper returns everything in one structured response. The Packager writes the files.

4. **Rich Progress Integration Point**
   - What we know: The conductor currently uses print() for phase banners. Rich needs to replace this.
   - What's unclear: Whether to inject a progress display into the conductor or wrap the conductor.run() externally.
   - Recommendation: Inject a PipelineProgress object into the Conductor (optional parameter). The conductor calls progress.phase_start() and progress.phase_complete() instead of print(). When no progress object is provided (e.g., tests), fall back to current print() behavior.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x --timeout=10` |
| Full suite command | `uv run pytest tests/ --timeout=10` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-01 | Mapper produces SkillDraft < 500 lines | unit | `uv run pytest tests/test_mapper_agent.py -x` | Wave 0 |
| PROD-02 | SkillDraft has YAML frontmatter with trigger description | unit | `uv run pytest tests/test_mapper_agent.py::test_has_frontmatter -x` | Wave 0 |
| PROD-03 | SkillDraft has worked examples for all use cases | unit | `uv run pytest tests/test_mapper_agent.py::test_worked_examples -x` | Wave 0 |
| PROD-04 | Reference sections extracted to references/ | unit | `uv run pytest tests/test_mapper_agent.py::test_reference_extraction -x` | Wave 0 |
| PROD-05 | Documenter produces SetupDraft with required sections | unit | `uv run pytest tests/test_documenter_agent.py -x` | Wave 0 |
| VAL-01 | Compactness evaluator catches > 500 lines | unit | `uv run pytest tests/test_evaluators.py::test_compactness -x` | Wave 0 |
| VAL-02 | Syntax evaluator catches invalid Python | unit | `uv run pytest tests/test_evaluators.py::test_syntax -x` | Wave 0 |
| VAL-03 | API accuracy evaluator returns structured score | unit | `uv run pytest tests/test_evaluators.py::test_api_accuracy -x` | Wave 0 |
| VAL-04 | Completeness evaluator returns structured score | unit | `uv run pytest tests/test_evaluators.py::test_completeness -x` | Wave 0 |
| VAL-05 | Trigger quality evaluator returns structured score | unit | `uv run pytest tests/test_evaluators.py::test_trigger_quality -x` | Wave 0 |
| VAL-06 | Scores < 7 trigger feedback routing | unit | `uv run pytest tests/test_conductor.py -x` | Exists (update) |
| PKG-01 | Packager assembles correct folder structure | unit | `uv run pytest tests/test_packager_agent.py::test_folder_structure -x` | Wave 0 |
| PKG-02 | Packager writes to correct deploy target path | unit | `uv run pytest tests/test_packager_agent.py::test_deploy_targets -x` | Wave 0 |
| PKG-03 | Pipeline prints verification instructions | unit | `uv run pytest tests/test_packager_agent.py::test_verification_instructions -x` | Wave 0 |
| CORE-10 | Rich progress shows phase/agent/status | unit | `uv run pytest tests/test_progress.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x --timeout=10`
- **Per wave merge:** `uv run pytest tests/ --timeout=10`
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- [ ] `tests/test_mapper_agent.py` -- covers PROD-01 through PROD-04
- [ ] `tests/test_documenter_agent.py` -- covers PROD-05
- [ ] `tests/test_evaluators.py` -- covers VAL-01 through VAL-05
- [ ] `tests/test_packager_agent.py` -- covers PKG-01 through PKG-03
- [ ] `tests/test_progress.py` -- covers CORE-10
- [ ] `tests/test_validator_agent.py` -- covers ValidatorAgent orchestration (fail-fast, parallel, unified result)
- [ ] Update `tests/test_conductor.py` -- covers VAL-06 (feedback routing with real failed_dimensions)

## Sources

### Primary (HIGH confidence)
- Existing codebase: conductor.py, stubs.py, models/production.py, models/evaluation.py -- exact I/O shapes and transition logic
- Existing Phase 2 agents: organizer.py, learner.py, gap_analyzer.py -- messages.parse pattern with Pydantic output_format
- [Rich Live Display docs](https://rich.readthedocs.io/en/latest/live.html) -- Live constructor, update(), console integration
- [Rich Progress docs](https://rich.readthedocs.io/en/stable/progress.html) -- Progress, SpinnerColumn, custom columns
- [Python ast module docs](https://docs.python.org/3/library/ast.html) -- ast.parse for syntax validation
- [Claude Code Skills docs](https://code.claude.com/docs/en/skills) -- SKILL.md format, frontmatter, deploy locations
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) -- trigger descriptions, 500-line limit, progressive disclosure, naming conventions

### Secondary (MEDIUM confidence)
- [Anthropic structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- messages.parse with output_format
- [Rich Console API](https://rich.readthedocs.io/en/latest/console.html) -- is_terminal, TTY_COMPATIBLE, TTY_INTERACTIVE env vars
- [Rich PyPI](https://pypi.org/project/rich/) -- current version 14.2.0 (Jan 2026)

### Tertiary (LOW confidence)
- LLM-as-judge scoring rubric best practices -- community patterns, not project-verified. Rubric design is important but implementation will be iterated.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Rich is the obvious choice for terminal UI; no real alternatives. ast is stdlib. Anthropic SDK patterns proven in Phase 2.
- Architecture: HIGH -- Module structure follows existing Phase 2 patterns. Evaluator separation is clean. ValidatorAgent orchestration is straightforward.
- Pitfalls: HIGH -- Most pitfalls identified from direct codebase analysis (e.g., _build_kwargs gap, ast.parse limitations) and official docs.
- Skill format: HIGH -- Official Claude Code docs and best practices docs provide authoritative format specification.

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain -- Rich, ast, and Anthropic SDK are all mature)
