"""Resilient LangSmith tracing wrapper.

All LangSmith integration goes through this module. Tracing errors are
caught at this boundary and never propagate to the pipeline (RES-02).

Usage:
    client = create_traced_client()  # auto-traces all Anthropic calls

    @traceable_agent(name="harvest", phase="harvesting", agent_name="harvester")
    def run_harvest(state):
        ...
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from anthropic import Anthropic

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _try_wrap_anthropic(client: Anthropic) -> Anthropic:
    """Attempt to wrap an Anthropic client with LangSmith tracing.

    Separated into its own function for testability (can be patched).
    """
    from langsmith.wrappers import wrap_anthropic

    return wrap_anthropic(client)


def create_traced_client() -> Anthropic:
    """Create an Anthropic client with LangSmith tracing.

    Falls back to an untraced client if LangSmith is unavailable or errors.
    Per RES-02: tracing errors never crash the pipeline.
    """
    client = Anthropic()
    try:
        client = _try_wrap_anthropic(client)
        logger.debug("LangSmith tracing enabled")
    except Exception:
        logger.warning("LangSmith tracing unavailable; running without tracing")
    return client


def _try_get_traceable() -> Callable[..., Any] | None:
    """Attempt to import LangSmith's @traceable decorator."""
    try:
        from langsmith import traceable

        return traceable
    except Exception:
        return None


def traceable_agent(
    name: str,
    phase: str,
    agent_name: str,
    iteration: int = 0,
) -> Callable[[F], F]:
    """Decorator factory for LangSmith @traceable with standard metadata.

    If LangSmith is unavailable, returns a no-op decorator that just
    calls the function directly. Per RES-02: tracing errors never
    propagate to the pipeline.

    Args:
        name: Operation name for the trace span.
        phase: Pipeline phase (e.g., "harvesting", "validating").
        agent_name: Agent identifier (e.g., "harvester", "validator").
        iteration: Loop iteration number (for feedback loops).
    """
    traceable_fn = _try_get_traceable()

    def decorator(fn: F) -> F:
        if traceable_fn is not None:
            try:
                wrapped = traceable_fn(
                    name=name,
                    run_type="chain",
                    tags=[f"phase:{phase}"],
                    metadata={
                        "agent": agent_name,
                        "iteration": iteration,
                    },
                )(fn)
                return wrapped  # type: ignore[return-value]
            except Exception:
                logger.warning(
                    "Failed to apply @traceable to %s; running without tracing",
                    fn.__name__,
                )

        @functools.wraps(fn)
        def passthrough(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return passthrough  # type: ignore[return-value]

    return decorator
