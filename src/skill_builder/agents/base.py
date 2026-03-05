"""Base agent protocol -- minimal contract for all pipeline agents.

Defines the interface that both stub and real agent implementations follow.
Real agents are implemented in Phase 2 and Phase 3.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class BaseAgent(Protocol):
    """Protocol for pipeline agents.

    Each agent accepts pipeline state (or relevant input) and returns
    a Pydantic model (or dict for packager). Only the conductor
    reads/writes PipelineState -- agents receive focused input and
    return focused output.
    """

    def run(self, **kwargs: Any) -> BaseModel | dict[str, Any]:
        """Execute the agent and return its output."""
        ...
