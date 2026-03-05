"""Stub agents -- return fixture data for all pipeline phases.

Used in Phase 1 to test the conductor state machine without real LLM calls.
Each stub returns a valid Pydantic model instance with hardcoded fixture data.

Fixture data covers:
(a) Happy path through all phases
(b) Gap analysis failure (force_insufficient=True)
(c) Validation failure (force_fail=True)
(d) Budget exceeded (handled by conductor, not stubs)
"""

from __future__ import annotations

from typing import Any

from skill_builder.models.brief import SeedUrl, SkillBrief
from skill_builder.models.evaluation import EvaluationDimension, EvaluationResult
from skill_builder.models.harvest import HarvestPage, HarvestResult
from skill_builder.models.production import SetupDraft, SkillDraft
from skill_builder.models.synthesis import (
    CategorizedResearch,
    ContentItem,
    GapReport,
    KnowledgeModel,
    ResearchCategory,
)


class StubIntakeAgent:
    """Validates the skill brief (pass-through in stub form)."""

    def run(self, **kwargs: Any) -> SkillBrief:
        """Return a validated SkillBrief with fixture data."""
        return SkillBrief(
            name="exa-tavily-firecrawl",
            description="Research crawling with Exa, Tavily, and Firecrawl",
            seed_urls=[
                SeedUrl(url="https://docs.exa.ai/", type="docs"),
                SeedUrl(url="https://docs.tavily.com/", type="docs"),
                SeedUrl(url="https://docs.firecrawl.dev/", type="docs"),
            ],
            tool_category="research",
            scope="Comprehensive research crawling",
            required_capabilities=["semantic search", "web search", "site crawling"],
            deploy_target="user",
        )


class StubHarvestAgent:
    """Returns fixture harvest data with 3 pages."""

    def run(self, **kwargs: Any) -> HarvestResult:
        """Return a HarvestResult with 3 fake pages."""
        pages = [
            HarvestPage(
                url="https://docs.exa.ai/getting-started",
                title="Exa Getting Started",
                content="Exa is a semantic search API...",
                source_type="crawl",
            ),
            HarvestPage(
                url="https://docs.tavily.com/quickstart",
                title="Tavily Quick Start",
                content="Tavily provides web search for AI agents...",
                source_type="crawl",
            ),
            HarvestPage(
                url="https://docs.firecrawl.dev/introduction",
                title="Firecrawl Introduction",
                content="Firecrawl turns websites into LLM-ready data...",
                source_type="crawl",
            ),
        ]
        return HarvestResult(pages=pages, total_pages=3)


class StubOrganizerAgent:
    """Returns fixture categorized research with 3 categories."""

    def run(self, **kwargs: Any) -> CategorizedResearch:
        """Return a CategorizedResearch with 3 categories."""
        categories = [
            ResearchCategory(
                name="installation",
                content=[
                    ContentItem(text="pip install exa-py", source_url="https://docs.exa.ai/"),
                    ContentItem(
                        text="pip install tavily-python", source_url="https://docs.tavily.com/"
                    ),
                    ContentItem(
                        text="pip install firecrawl-py", source_url="https://docs.firecrawl.dev/"
                    ),
                ],
            ),
            ResearchCategory(
                name="core-concepts",
                content=[
                    ContentItem(
                        text="Exa uses neural search for semantic retrieval",
                        source_url="https://docs.exa.ai/",
                    ),
                    ContentItem(
                        text="Tavily optimizes web search for AI applications",
                        source_url="https://docs.tavily.com/",
                    ),
                    ContentItem(
                        text="Firecrawl converts websites to structured data",
                        source_url="https://docs.firecrawl.dev/",
                    ),
                ],
            ),
            ResearchCategory(
                name="authentication",
                content=[
                    ContentItem(
                        text="Exa requires EXA_API_KEY", source_url="https://docs.exa.ai/"
                    ),
                    ContentItem(
                        text="Tavily requires TAVILY_API_KEY",
                        source_url="https://docs.tavily.com/",
                    ),
                    ContentItem(
                        text="Firecrawl requires FIRECRAWL_API_KEY",
                        source_url="https://docs.firecrawl.dev/",
                    ),
                ],
            ),
        ]
        return CategorizedResearch(categories=categories, source_count=3)


class StubGapAnalyzerAgent:
    """Returns gap analysis with configurable sufficiency."""

    def run(self, *, force_insufficient: bool = False, **kwargs: Any) -> GapReport:
        """Return a GapReport.

        Args:
            force_insufficient: When True, returns is_sufficient=False with
                gaps and search queries (simulates gap analysis failure).
        """
        if force_insufficient:
            return GapReport(
                is_sufficient=False,
                identified_gaps=[
                    "Missing batch operation examples",
                    "No rate limiting documentation found",
                    "Authentication flow unclear for Firecrawl v4",
                ],
                recommended_search_queries=[
                    "firecrawl batch crawl API",
                    "exa rate limits",
                    "firecrawl v4 authentication",
                ],
            )
        return GapReport(
            is_sufficient=True,
            identified_gaps=[],
            recommended_search_queries=[],
        )


class StubLearnerAgent:
    """Returns fixture knowledge model data."""

    def run(self, **kwargs: Any) -> KnowledgeModel:
        """Return a KnowledgeModel with fixture data."""
        return KnowledgeModel(
            canonical_use_cases=[
                "Deep research on a topic using multiple search APIs",
                "Crawling documentation sites for LLM training data",
                "Combining semantic and keyword search for comprehensive coverage",
            ],
            required_parameters=[
                "EXA_API_KEY: str",
                "TAVILY_API_KEY: str",
                "FIRECRAWL_API_KEY: str",
            ],
            common_gotchas=[
                "Exa search results are semantic, not keyword-based",
                "Firecrawl has page limits per crawl session",
                "Tavily results may overlap with Exa results",
            ],
            best_practices=[
                "Use Exa for semantic discovery, Tavily for current events, "
                "Firecrawl for deep site crawls",
                "Deduplicate results across all three sources",
                "Set reasonable page limits to control costs",
            ],
            anti_patterns=[
                "Using all three APIs for the same query without deduplication",
                "Ignoring rate limits on batch operations",
            ],
            dependencies=["exa-py>=1.0", "tavily-python>=0.3", "firecrawl-py>=1.0"],
            minimum_viable_example=(
                "from exa_py import Exa\n"
                "exa = Exa(api_key='...')\n"
                "results = exa.search('machine learning frameworks')\n"
            ),
            trigger_phrases=[
                "research using exa",
                "search with tavily",
                "crawl with firecrawl",
            ],
        )


class StubMapperAgent:
    """Returns fixture SKILL.md draft content."""

    def run(self, **kwargs: Any) -> SkillDraft:
        """Return a SkillDraft with fixture markdown content."""
        content = """---
name: exa-tavily-firecrawl
description: Research crawling with Exa, Tavily, and Firecrawl
---

# Exa + Tavily + Firecrawl Research Skill

## Overview
Use Exa for semantic search, Tavily for web search, and Firecrawl for deep site crawling.

## Usage
```python
from exa_py import Exa
exa = Exa(api_key='...')
results = exa.search('your query')
```
"""
        return SkillDraft(
            content=content,
            line_count=content.count("\n") + 1,
            has_frontmatter=True,
        )


class StubDocumenterAgent:
    """Returns fixture SETUP.md draft content."""

    def run(self, **kwargs: Any) -> SetupDraft:
        """Return a SetupDraft with fixture content."""
        content = """# Setup Guide

## Prerequisites
- Python 3.12+
- API keys for Exa, Tavily, and Firecrawl

## Quick Start
1. Install dependencies: `pip install exa-py tavily-python firecrawl-py`
2. Set environment variables: `EXA_API_KEY`, `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`
3. Run: `skill-builder build examples/exa-tavily-firecrawl.json`
"""
        return SetupDraft(
            content=content,
            has_prerequisites=True,
            has_quick_start=True,
        )


class StubValidatorAgent:
    """Returns evaluation results with configurable pass/fail."""

    def run(
        self, *, force_fail: bool = False, iteration: int = 1, **kwargs: Any
    ) -> EvaluationResult:
        """Return an EvaluationResult.

        Args:
            force_fail: When True, returns overall_pass=False with low scores.
            iteration: Which validation iteration this is (1-based).
        """
        if force_fail:
            return EvaluationResult(
                dimensions=[
                    EvaluationDimension(
                        name="api_accuracy",
                        score=4,
                        feedback="Multiple API methods incorrect",
                        passed=False,
                    ),
                    EvaluationDimension(
                        name="completeness",
                        score=5,
                        feedback="Missing batch operation docs",
                        passed=False,
                    ),
                    EvaluationDimension(
                        name="code_quality",
                        score=6,
                        feedback="Examples need error handling",
                        passed=False,
                    ),
                ],
                overall_pass=False,
                iteration=iteration,
            )
        return EvaluationResult(
            dimensions=[
                EvaluationDimension(
                    name="api_accuracy", score=9, feedback="All API methods verified", passed=True
                ),
                EvaluationDimension(
                    name="completeness", score=8, feedback="All capabilities covered", passed=True
                ),
                EvaluationDimension(
                    name="code_quality", score=9, feedback="Clean, runnable examples", passed=True
                ),
            ],
            overall_pass=True,
            iteration=iteration,
        )


class StubPackagerAgent:
    """Returns a dict with the package output path."""

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Return a dict with package_path pointing to the output directory."""
        return {
            "package_path": ".skill-builder/output/exa-tavily-firecrawl",
        }
