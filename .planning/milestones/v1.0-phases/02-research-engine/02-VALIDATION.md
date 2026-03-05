---
phase: 2
slug: research-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x --timeout=10` |
| **Full suite command** | `uv run pytest tests/ --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x --timeout=10`
- **After every plan wave:** Run `uv run pytest tests/ --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | HARV-01 | unit | `uv run pytest tests/test_harvest_router.py -x` | Wave 0 | ⬜ pending |
| 02-01-02 | 01 | 0 | HARV-02 | unit (mocked) | `uv run pytest tests/test_firecrawl_strategy.py -x` | Wave 0 | ⬜ pending |
| 02-01-03 | 01 | 0 | HARV-03 | unit (mocked) | `uv run pytest tests/test_harvest_router.py::test_api_schema_fallback -x` | Wave 0 | ⬜ pending |
| 02-01-04 | 01 | 0 | HARV-04 | unit | `uv run pytest tests/test_version_check.py -x` | Wave 0 | ⬜ pending |
| 02-01-05 | 01 | 0 | HARV-05 | unit (mocked) | `uv run pytest tests/test_exa_strategy.py -x` | Wave 0 | ⬜ pending |
| 02-01-06 | 01 | 0 | HARV-06 | unit (mocked) | `uv run pytest tests/test_tavily_strategy.py -x` | Wave 0 | ⬜ pending |
| 02-01-07 | 01 | 0 | HARV-07 | unit | `uv run pytest tests/test_dedup.py -x` | Wave 0 | ⬜ pending |
| 02-01-08 | 01 | 0 | HARV-08 | unit | `uv run pytest tests/test_version_check.py -x` | Wave 0 | ⬜ pending |
| 02-01-09 | 01 | 0 | HARV-09 | unit (mocked) | `uv run pytest tests/test_saturation.py -x` | Wave 0 | ⬜ pending |
| 02-01-10 | 01 | 0 | HARV-10 | integration (mocked) | `uv run pytest tests/test_harvest_agent.py::test_parallel -x` | Wave 0 | ⬜ pending |
| 02-02-01 | 02 | 0 | SYNTH-01 | unit (mocked) | `uv run pytest tests/test_organizer_agent.py -x` | Wave 0 | ⬜ pending |
| 02-02-02 | 02 | 0 | SYNTH-02 | unit (mocked) | `uv run pytest tests/test_gap_analyzer_agent.py -x` | Wave 0 | ⬜ pending |
| 02-02-03 | 02 | 0 | SYNTH-03 | unit | `uv run pytest tests/test_models.py::test_gap_report -x` | Exists | ⬜ pending |
| 02-02-04 | 02 | 0 | SYNTH-04 | unit (mocked) | `uv run pytest tests/test_gap_analyzer_agent.py::test_missing_capability -x` | Wave 0 | ⬜ pending |
| 02-02-05 | 02 | 0 | SYNTH-05 | unit (mocked) | `uv run pytest tests/test_learner_agent.py -x` | Wave 0 | ⬜ pending |
| 02-02-06 | 02 | 0 | SYNTH-06 | unit | `uv run pytest tests/test_models.py -x` | Partially exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_harvest_router.py` — stubs for HARV-01, HARV-03
- [ ] `tests/test_firecrawl_strategy.py` — stubs for HARV-02
- [ ] `tests/test_exa_strategy.py` — stubs for HARV-05
- [ ] `tests/test_tavily_strategy.py` — stubs for HARV-06
- [ ] `tests/test_dedup.py` — stubs for HARV-07
- [ ] `tests/test_version_check.py` — stubs for HARV-04, HARV-08
- [ ] `tests/test_saturation.py` — stubs for HARV-09
- [ ] `tests/test_harvest_agent.py` — stubs for HARV-10 (integration with mocked APIs)
- [ ] `tests/test_organizer_agent.py` — stubs for SYNTH-01
- [ ] `tests/test_gap_analyzer_agent.py` — stubs for SYNTH-02, SYNTH-04
- [ ] `tests/test_learner_agent.py` — stubs for SYNTH-05
- [ ] `tests/test_query_generator.py` — stubs for search query generation
- [ ] Install new deps: `uv add "firecrawl-py>=4.18,<5" "exa-py>=2.7,<3" "tavily-python>=0.7,<1"`

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
