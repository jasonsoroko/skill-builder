"""Pipeline state model -- the full persistent state of a skill-builder run.

PipelineState is serialized to JSON at every phase boundary for checkpoint
persistence. PipelinePhase is a str Enum for clean JSON output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PipelinePhase(StrEnum):
    """Pipeline phase identifiers.

    Uses StrEnum so values are JSON-serializable strings.
    """

    INITIALIZED = "initialized"
    INTAKE = "intake"
    HARVESTING = "harvesting"
    ORGANIZING = "organizing"
    GAP_ANALYZING = "gap_analyzing"
    RE_HARVESTING = "re_harvesting"
    LEARNING = "learning"
    MAPPING = "mapping"
    DOCUMENTING = "documenting"
    VALIDATING = "validating"
    RE_PRODUCING = "re_producing"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    FAILED = "failed"


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(UTC)


class PipelineState(BaseModel):
    """Full pipeline state -- serialized to JSON at phase boundaries.

    Phase output fields are dict | None placeholders. Real typed models
    will be used in Phase 2+ when agents produce actual output.
    """

    phase: PipelinePhase = PipelinePhase.INITIALIZED
    brief_name: str

    # Phase outputs (populated as pipeline progresses)
    raw_harvest: dict | None = None  # type: ignore[type-arg]
    categorized_research: dict | None = None  # type: ignore[type-arg]
    gap_report: dict | None = None  # type: ignore[type-arg]
    knowledge_model: dict | None = None  # type: ignore[type-arg]
    skill_draft: dict | None = None  # type: ignore[type-arg]
    setup_draft: dict | None = None  # type: ignore[type-arg]
    evaluation_results: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]
    package_path: str | None = None
    verification_instructions: str | None = None

    # Loop counters
    gap_loop_count: int = 0
    validation_loop_count: int = 0

    # Budget tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    # Metadata
    error: str | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
