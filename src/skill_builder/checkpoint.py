"""Checkpoint store -- JSON persistence of PipelineState.

Saves and loads PipelineState to/from JSON files in a state directory.
Used by the conductor to persist state at every phase boundary and
support resume from any checkpoint.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from skill_builder.models.state import PipelineState

logger = logging.getLogger(__name__)


class CheckpointStore:
    """JSON-based checkpoint store for PipelineState.

    State files are written to {state_dir}/{brief_name}.json using
    Pydantic's model_dump_json() / model_validate_json() for correct
    handling of datetime, enum, and optional fields.
    """

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, brief_name: str) -> Path:
        """Return the file path for a given brief name."""
        return self.state_dir / f"{brief_name}.json"

    def save(self, state: PipelineState) -> None:
        """Save pipeline state to JSON, updating the updated_at timestamp."""
        state.updated_at = datetime.now(UTC)
        self._path(state.brief_name).write_text(state.model_dump_json(indent=2))
        logger.debug("Saved checkpoint for '%s' at phase %s", state.brief_name, state.phase)

    def load(self, brief_name: str) -> PipelineState | None:
        """Load pipeline state from JSON, or return None if not found."""
        path = self._path(brief_name)
        if not path.exists():
            return None
        loaded = PipelineState.model_validate_json(path.read_text())
        logger.debug("Loaded checkpoint for '%s' at phase %s", brief_name, loaded.phase)
        return loaded

    def exists(self, brief_name: str) -> bool:
        """Check whether a state file exists for the given brief name."""
        return self._path(brief_name).exists()
