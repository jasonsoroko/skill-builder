---
phase: 3
slug: output-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/ -x --timeout=10` |
| **Full suite command** | `uv run pytest tests/ --timeout=10` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x --timeout=10`
- **After every plan wave:** Run `uv run pytest tests/ --timeout=10`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PROD-01 | unit | `uv run pytest tests/test_mapper_agent.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PROD-02 | unit | `uv run pytest tests/test_mapper_agent.py::test_has_frontmatter -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PROD-03 | unit | `uv run pytest tests/test_mapper_agent.py::test_worked_examples -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | PROD-04 | unit | `uv run pytest tests/test_mapper_agent.py::test_reference_extraction -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | PROD-05 | unit | `uv run pytest tests/test_documenter_agent.py -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | VAL-01 | unit | `uv run pytest tests/test_evaluators.py::test_compactness -x` | ❌ W0 | ⬜ pending |
| 03-01-07 | 01 | 1 | VAL-02 | unit | `uv run pytest tests/test_evaluators.py::test_syntax -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | VAL-03 | unit | `uv run pytest tests/test_evaluators.py::test_api_accuracy -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | VAL-04 | unit | `uv run pytest tests/test_evaluators.py::test_completeness -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | VAL-05 | unit | `uv run pytest tests/test_evaluators.py::test_trigger_quality -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | VAL-06 | unit | `uv run pytest tests/test_conductor.py -x` | ✅ (update) | ⬜ pending |
| 03-03-01 | 03 | 2 | PKG-01 | unit | `uv run pytest tests/test_packager_agent.py::test_folder_structure -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | PKG-02 | unit | `uv run pytest tests/test_packager_agent.py::test_deploy_targets -x` | ❌ W0 | ⬜ pending |
| 03-03-03 | 03 | 2 | PKG-03 | unit | `uv run pytest tests/test_packager_agent.py::test_verification_instructions -x` | ❌ W0 | ⬜ pending |
| 03-03-04 | 03 | 2 | CORE-10 | unit | `uv run pytest tests/test_progress.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mapper_agent.py` — stubs for PROD-01 through PROD-04
- [ ] `tests/test_documenter_agent.py` — stubs for PROD-05
- [ ] `tests/test_evaluators.py` — stubs for VAL-01 through VAL-05
- [ ] `tests/test_validator_agent.py` — ValidatorAgent orchestration (fail-fast, parallel, unified result)
- [ ] `tests/test_packager_agent.py` — stubs for PKG-01 through PKG-03
- [ ] `tests/test_progress.py` — stubs for CORE-10
- [ ] Update `tests/test_conductor.py` — VAL-06 (feedback routing with real failed_dimensions)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich Live display renders correctly in terminal | CORE-10 | Visual rendering requires TTY inspection | Run `uv run skill-builder build` and visually confirm status panel updates |
| Deploy to ~/.claude/skills/ works | PKG-02 | Requires user-scope file system access | Run with `--deploy-target user` and verify files at ~/.claude/skills/{name}/ |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
