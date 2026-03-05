"""Synthesis phase data models.

These models represent the output of the synthesis agents: organized research,
gap analysis reports, and the final knowledge model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchCategory(BaseModel):
    """A single category of organized research."""

    name: str = Field(description="Category name (e.g., installation, core concepts)")
    content: list[str] = Field(default_factory=list, description="Content items in this category")


class CategorizedResearch(BaseModel):
    """Organized research output from the Organizer agent."""

    categories: list[ResearchCategory] = Field(
        default_factory=list, description="Research organized by category"
    )
    source_count: int = Field(default=0, description="Number of sources processed")


class GapReport(BaseModel):
    """Output from the Gap Analyzer agent."""

    is_sufficient: bool = Field(description="Whether research covers all required capabilities")
    identified_gaps: list[str] = Field(
        default_factory=list, description="Gaps found in the research"
    )
    recommended_search_queries: list[str] = Field(
        default_factory=list, description="Queries to fill identified gaps"
    )


class KnowledgeModel(BaseModel):
    """Structured knowledge extracted by the Learner agent.

    This is the primary input to the production phase.
    """

    canonical_use_cases: list[str] = Field(
        default_factory=list, description="Primary use cases for the tool"
    )
    required_parameters: list[str] = Field(
        default_factory=list, description="Required parameters and their types"
    )
    common_gotchas: list[str] = Field(
        default_factory=list, description="Common mistakes and how to avoid them"
    )
    best_practices: list[str] = Field(
        default_factory=list, description="Recommended patterns and practices"
    )
    anti_patterns: list[str] = Field(
        default_factory=list, description="Patterns to avoid"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Required dependencies and versions"
    )
    minimum_viable_example: str = Field(
        default="", description="Smallest working example of the tool"
    )
    trigger_phrases: list[str] = Field(
        default_factory=list, description="Phrases that should activate this skill"
    )
