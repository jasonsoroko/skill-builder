"""Pipeline agents for skill-builder.

Re-exports real agent implementations for Phase 2 and Phase 3 agents,
plus stub agents for intake and packager (not yet implemented).
"""

from skill_builder.agents.documenter import DocumenterAgent
from skill_builder.agents.gap_analyzer import GapAnalyzerAgent
from skill_builder.agents.harvest import HarvestAgent
from skill_builder.agents.learner import LearnerAgent
from skill_builder.agents.mapper import MapperAgent
from skill_builder.agents.organizer import OrganizerAgent
from skill_builder.agents.stubs import (
    StubDocumenterAgent,
    StubGapAnalyzerAgent,
    StubHarvestAgent,
    StubIntakeAgent,
    StubLearnerAgent,
    StubMapperAgent,
    StubOrganizerAgent,
    StubPackagerAgent,
    StubValidatorAgent,
)
from skill_builder.agents.validator import ValidatorAgent

__all__ = [
    # Real Phase 2 agents
    "GapAnalyzerAgent",
    "HarvestAgent",
    "LearnerAgent",
    "OrganizerAgent",
    # Real Phase 3 agents
    "DocumenterAgent",
    "MapperAgent",
    "ValidatorAgent",
    # Stub agents (for testing and unimplemented phases)
    "StubDocumenterAgent",
    "StubGapAnalyzerAgent",
    "StubHarvestAgent",
    "StubIntakeAgent",
    "StubLearnerAgent",
    "StubMapperAgent",
    "StubOrganizerAgent",
    "StubPackagerAgent",
    "StubValidatorAgent",
]
