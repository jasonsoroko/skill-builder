# Phase 4: Deferred Items

## Pre-existing Test Failure

- **Test:** `tests/test_tracing.py::TestTracingIntegration::test_traceable_agent_applied_to_run`
- **Issue:** Test expects `traceable_agent` import in `conductor.py`, but the tracing wiring hasn't been implemented yet. This is a Plan 02/03 concern (OBS-02 tracing wiring).
- **Discovered during:** Plan 04-01 execution
- **Action:** Will be resolved when Plan 02/03 wires tracing into conductor.
