"""Synthesis phase data models.

These models represent the output of the synthesis agents: organized research,
gap analysis reports, and the final knowledge model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """A content item with source attribution."""

    text: str = Field(description="The content text")
    source_url: str = Field(description="URL where this content originated")


class ResearchCategory(BaseModel):
    """A single category of organized research."""

    name: str = Field(description="Category name (e.g., installation, core concepts)")
    content: list[ContentItem] = Field(
        default_factory=list, description="Content items with source attribution"
    )


class CategorizedResearch(BaseModel):
    """Organized research output from the Organizer agent."""

    categories: list[ResearchCategory] = Field(
        default_factory=list, description="Research organized by category"
    )
    source_count: int = Field(default=0, description="Number of sources processed")
    tools_covered: list[str] = Field(
        default_factory=list, description="Which tools had content"
    )


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


class GeneratedQueries(BaseModel):
    """LLM-generated search queries for Exa and Tavily."""

    exa_queries: list[str] = Field(description="Semantic search queries for Exa")
    tavily_queries: list[str] = Field(description="Factual search queries for Tavily")


class SaturationResult(BaseModel):
    """Result of the lightweight saturation pre-filter check."""

    is_saturated: bool = Field(description="Whether harvested content covers required capabilities")
    missing_capabilities: list[str] = Field(
        default_factory=list, description="Required capabilities with no content"
    )
