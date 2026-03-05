"""Pipeline agents for skill-builder.

Re-exports real agent implementations for Phase 2 and stub agents
for Phase 3 phases that are not yet implemented.
"""

from skill_builder.agents.gap_analyzer import GapAnalyzerAgent
from skill_builder.agents.harvest import HarvestAgent
from skill_builder.agents.learner import LearnerAgent
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

__all__ = [
    # Real Phase 2 agents
    "GapAnalyzerAgent",
    "HarvestAgent",
    "LearnerAgent",
    "OrganizerAgent",
    # Stub agents (Phase 1 / Phase 3)
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
