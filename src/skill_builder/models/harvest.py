"""Harvest phase data models.

These models represent the output of the content harvesting phase:
raw pages fetched from seed URLs and supplemental searches.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HarvestPage(BaseModel):
    """A single page of harvested content."""

    url: str = Field(description="Source URL")
    title: str = Field(description="Page title")
    content: str = Field(description="Extracted text content")
    source_type: str = Field(description="How this page was found (crawl, search, api)")
    content_hash: str | None = Field(default=None, description="Hash for deduplication")


class HarvestResult(BaseModel):
    """Aggregated result of a harvest phase."""

    pages: list[HarvestPage] = Field(default_factory=list, description="All harvested pages")
    total_pages: int = Field(default=0, description="Total page count")
    fetch_plan: dict | None = Field(default=None, description="Plan used for fetching")  # type: ignore[type-arg]
