---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (Wave 0 creates) |
| **Quick run command** | `pytest tests/ -x --timeout=10` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --timeout=10`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | CORE-01 | unit | `pytest tests/test_models.py::test_skill_brief_valid -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | CORE-01 | unit | `pytest tests/test_models.py::test_skill_brief_invalid -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | CORE-02 | unit | `pytest tests/test_conductor.py::test_happy_path -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | CORE-03 | unit | `pytest tests/test_conductor.py::test_gap_loop -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | CORE-04 | unit | `pytest tests/test_conductor.py::test_validation_loop -x` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 1 | CORE-05 | unit | `pytest tests/test_checkpoint.py::test_save_load_roundtrip -x` | ❌ W0 | ⬜ pending |
| 01-02-05 | 02 | 1 | CORE-06 | integration | `pytest tests/test_conductor.py::test_resume_from_checkpoint -x` | ❌ W0 | ⬜ pending |
| 01-02-06 | 02 | 1 | CORE-08 | unit | `pytest tests/test_budget.py::test_budget_exceeded -x` | ❌ W0 | ⬜ pending |
| 01-02-07 | 02 | 1 | RES-03 | unit | `pytest tests/test_conductor.py::test_loop_caps -x` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 1 | CORE-07 | integration | `pytest tests/test_cli.py::test_dry_run -x` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 1 | CORE-09 | unit | `pytest tests/test_cli.py::test_cli_options -x` | ❌ W0 | ⬜ pending |
| 01-03-03 | 03 | 1 | OBS-01 | unit | `pytest tests/test_tracing.py::test_wrap_anthropic -x` | ❌ W0 | ⬜ pending |
| 01-03-04 | 03 | 1 | OBS-02 | unit | `pytest tests/test_tracing.py::test_metadata_tags -x` | ❌ W0 | ⬜ pending |
| 01-03-05 | 03 | 1 | RES-01 | unit | `pytest tests/test_resilience.py::test_exponential_backoff -x` | ❌ W0 | ⬜ pending |
| 01-03-06 | 03 | 1 | RES-02 | unit | `pytest tests/test_tracing.py::test_tracing_failure_resilience -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — project metadata, dependencies, pytest config, ruff config, CLI entry point
- [ ] `tests/conftest.py` — shared fixtures (sample brief JSON, mock Anthropic client, tmp state dir)
- [ ] `tests/test_models.py` — stubs for CORE-01 (brief validation)
- [ ] `tests/test_conductor.py` — stubs for CORE-02, CORE-03, CORE-04, CORE-06, RES-03
- [ ] `tests/test_checkpoint.py` — stubs for CORE-05
- [ ] `tests/test_budget.py` — stubs for CORE-08
- [ ] `tests/test_cli.py` — stubs for CORE-07, CORE-09
- [ ] `tests/test_tracing.py` — stubs for OBS-01, OBS-02, RES-02
- [ ] `tests/test_resilience.py` — stubs for RES-01
- [ ] Framework install: `uv pip install -e ".[dev]"`

*All test files are Wave 0 — created before implementation begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OBS-03: Cost tracking in LangSmith | OBS-03 | Requires live LangSmith connection | Run a build, check LangSmith dashboard for cost/token data |
| Phase banner visual appearance | CONTEXT | Subjective visual quality | Run `skill-builder build examples/exa-tavily-firecrawl.json` and inspect terminal output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
