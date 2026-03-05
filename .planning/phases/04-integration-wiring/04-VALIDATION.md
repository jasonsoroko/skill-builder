---
phase: 4
slug: integration-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.0 with pytest-asyncio >= 0.25 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -x --timeout=10` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -v --timeout=10` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -x --timeout=10`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -v --timeout=10`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | CORE-08 | unit | `.venv/bin/python -m pytest tests/test_conductor.py::TestBudgetRecording -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | CORE-08 | unit | `.venv/bin/python -m pytest tests/test_conductor.py::TestBudgetExceeded -x` | ✅ partial | ⬜ pending |
| 04-01-03 | 01 | 1 | RES-01 | unit | `.venv/bin/python -m pytest tests/test_resilience.py::TestUnifiedRetry -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | RES-01 | unit | `.venv/bin/python -m pytest tests/test_resilience.py::TestRetryVisibility -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | OBS-02 | unit | `.venv/bin/python -m pytest tests/test_tracing.py::TestTracingIntegration -x` | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 1 | HARV-08 | unit | `.venv/bin/python -m pytest tests/test_harvest_agent.py::TestVersionPersistence -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_resilience.py` — add TestUnifiedRetry class for non-Anthropic SDK exceptions
- [ ] `tests/test_resilience.py` — add TestRetryVisibility class for CLI output
- [ ] `tests/test_conductor.py` — add TestBudgetRecording class for usage metadata extraction
- [ ] `tests/test_harvest_agent.py` — add TestVersionPersistence class for detected_version fix
- [ ] `tests/test_tracing.py` — add TestTracingIntegration class for conductor dispatch tracing

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LangSmith spans visible in UI | OBS-02 | Requires live LangSmith account | Configure LANGSMITH_API_KEY, run pipeline, verify spans in LangSmith dashboard |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
