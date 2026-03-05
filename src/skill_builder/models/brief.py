"""SkillBrief model -- the input contract for the skill-builder pipeline.

A skill brief describes what skill to build: seed URLs to crawl, the tool
category, scope, required capabilities, and deployment target. The conductor
loads this file at intake and uses it to drive the entire pipeline.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class SeedUrl(BaseModel):
    """A typed URL for content routing.

    The `type` field gives the content router a hint about extraction strategy
    before it validates at harvest time.
    """

    url: str = Field(min_length=1, description="URL to crawl or fetch")
    type: Literal["docs", "github", "api_schema", "blog"] = Field(
        description="Source type hint for content routing"
    )


class SkillBrief(BaseModel):
    """Structured input that describes what skill to build.

    Required fields fail fast with specific error messages. Optional fields
    get sensible defaults.
    """

    name: str = Field(min_length=1, description="Skill name (used for file naming)")
    description: str = Field(min_length=1, description="What this skill does")
    seed_urls: list[SeedUrl] = Field(min_length=1, description="URLs to crawl for research")
    tool_category: str = Field(min_length=1, description="Category (e.g., research, dev-tools)")
    scope: str = Field(min_length=1, description="What the skill covers")
    required_capabilities: list[str] = Field(
        min_length=1, description="Capabilities the skill must cover"
    )
    deploy_target: Literal["repo", "user", "package"] = Field(
        description="Where the skill will be installed"
    )
    target_api_version: str | None = Field(
        default=None, description="Specific API version to target (None = discover)"
    )
    max_pages: int = Field(default=50, ge=1, description="Max pages to crawl per source")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def brief_name(self) -> str:
        """Derive a slugified name for file naming and state keys."""
        slug = self.name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
