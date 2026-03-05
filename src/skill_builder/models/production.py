"""Production phase data models.

These models represent the output of the production agents:
the draft SKILL.md and SETUP.md files.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillDraft(BaseModel):
    """Draft SKILL.md content from the Mapper agent."""

    content: str = Field(description="Full SKILL.md content")
    line_count: int = Field(description="Number of lines in the draft")
    has_frontmatter: bool = Field(description="Whether YAML frontmatter is present")
    reference_files: dict[str, str] | None = Field(
        default=None,
        description="Reference files to extract (filename -> content)",
    )


class SetupDraft(BaseModel):
    """Draft SETUP.md content from the Documenter agent."""

    content: str = Field(description="Full SETUP.md content")
    has_prerequisites: bool = Field(description="Whether prerequisites section exists")
    has_quick_start: bool = Field(description="Whether quick start section exists")
