"""Tests for the PackagerAgent.

Covers:
- BaseAgent Protocol conformance
- Output folder assembly: SKILL.md, SETUP.md, references/, scripts/, assets/
- LICENSE.txt generation with MIT license and current year
- Deploy target path resolution (repo, user, package)
- Reference files written to references/ directory
- Return value with package_path and verification_instructions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, runtime_checkable
from unittest.mock import patch

import pytest

from skill_builder.agents.base import BaseAgent
from skill_builder.agents.packager import PackagerAgent, _resolve_deploy_path
from skill_builder.models.brief import SkillBrief


@pytest.fixture
def brief() -> SkillBrief:
    """Return a minimal valid SkillBrief for testing."""
    return SkillBrief(
        name="test-skill",
        description="A test skill",
        seed_urls=[{"url": "https://example.com", "type": "docs"}],
        tool_category="test",
        scope="testing",
        required_capabilities=["testing"],
        deploy_target="repo",
    )


@pytest.fixture
def skill_draft() -> dict[str, Any]:
    """Return a minimal skill draft dict."""
    return {
        "content": "---\nname: test-skill\n---\n\n# Test Skill\n\nSome content.\n",
        "line_count": 5,
        "has_frontmatter": True,
        "reference_files": None,
    }


@pytest.fixture
def skill_draft_with_refs() -> dict[str, Any]:
    """Return a skill draft with reference files."""
    return {
        "content": "---\nname: test-skill\n---\n\n# Test Skill\n\nSome content.\n",
        "line_count": 5,
        "has_frontmatter": True,
        "reference_files": {
            "api_reference.md": "# API Reference\n\nSome API docs.\n",
            "config_guide.md": "# Config Guide\n\nSome config docs.\n",
        },
    }


@pytest.fixture
def setup_draft() -> dict[str, Any]:
    """Return a minimal setup draft dict."""
    return {
        "content": "# Setup Guide\n\n## Prerequisites\n- Python 3.12+\n\n## Quick Start\n1. Install\n",
        "has_prerequisites": True,
        "has_quick_start": True,
    }


class TestProtocolConformance:
    """PackagerAgent conforms to BaseAgent Protocol."""

    def test_packager_is_base_agent(self) -> None:
        """PackagerAgent satisfies the BaseAgent Protocol (duck typing)."""
        agent = PackagerAgent()
        assert isinstance(agent, BaseAgent)

    def test_packager_has_run_method(self) -> None:
        """PackagerAgent has a run(**kwargs) method."""
        agent = PackagerAgent()
        assert callable(getattr(agent, "run", None))


class TestDeployPathResolution:
    """Test _resolve_deploy_path helper."""

    def test_repo_target(self) -> None:
        """'repo' deploy target resolves to .claude/skills/{name}/."""
        path = _resolve_deploy_path("repo", "test-skill")
        assert path == Path(".claude/skills/test-skill")

    def test_user_target(self) -> None:
        """'user' deploy target resolves to ~/.claude/skills/{name}/."""
        path = _resolve_deploy_path("user", "test-skill")
        expected = Path.home() / ".claude" / "skills" / "test-skill"
        assert path == expected

    def test_package_target(self) -> None:
        """'package' deploy target resolves to .skill-builder/output/{name}/."""
        path = _resolve_deploy_path("package", "test-skill")
        assert path == Path(".skill-builder/output/test-skill")

    def test_unknown_target_raises(self) -> None:
        """Unknown deploy target raises ValueError."""
        with pytest.raises(ValueError, match="Unknown deploy target"):
            _resolve_deploy_path("cloud", "test-skill")


class TestFolderAssembly:
    """PackagerAgent assembles correct folder structure."""

    def test_creates_skill_md(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """PackagerAgent writes SKILL.md with correct content."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            result = agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        skill_path = tmp_path / "output" / "SKILL.md"
        assert skill_path.exists()
        assert skill_path.read_text() == skill_draft["content"]

    def test_creates_setup_md(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """PackagerAgent writes SETUP.md with correct content."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        setup_path = tmp_path / "output" / "SETUP.md"
        assert setup_path.exists()
        assert setup_path.read_text() == setup_draft["content"]

    def test_creates_subdirectories(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """PackagerAgent creates references/, scripts/, assets/ subdirectories."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        assert (tmp_path / "output" / "references").is_dir()
        assert (tmp_path / "output" / "scripts").is_dir()
        assert (tmp_path / "output" / "assets").is_dir()

    def test_writes_license_txt(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """PackagerAgent writes LICENSE.txt with MIT license including current year."""
        import datetime

        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        license_path = tmp_path / "output" / "LICENSE.txt"
        assert license_path.exists()
        content = license_path.read_text()
        assert "MIT License" in content
        assert str(datetime.datetime.now(datetime.UTC).year) in content

    def test_writes_reference_files(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft_with_refs: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """When skill_draft has reference_files, they are written to references/."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            agent.run(
                skill_draft=skill_draft_with_refs, setup_draft=setup_draft, brief=brief
            )

        refs_dir = tmp_path / "output" / "references"
        assert (refs_dir / "api_reference.md").exists()
        assert (refs_dir / "config_guide.md").exists()
        assert (refs_dir / "api_reference.md").read_text() == "# API Reference\n\nSome API docs.\n"
        assert (refs_dir / "config_guide.md").read_text() == "# Config Guide\n\nSome config docs.\n"

    def test_no_reference_files_when_none(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """When skill_draft reference_files is None, references/ is empty."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        refs_dir = tmp_path / "output" / "references"
        assert refs_dir.is_dir()
        # Should be empty (no files written)
        assert list(refs_dir.iterdir()) == []


class TestReturnValue:
    """PackagerAgent returns dict with package_path and verification_instructions."""

    def test_returns_package_path(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """Return dict has 'package_path' key with string value."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            result = agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        assert "package_path" in result
        assert isinstance(result["package_path"], str)
        assert "output" in result["package_path"]

    def test_returns_verification_instructions(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """Return dict has 'verification_instructions' key with meaningful content."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            result = agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        assert "verification_instructions" in result
        instructions = result["verification_instructions"]
        assert isinstance(instructions, str)
        assert "verify" in instructions.lower() or "test" in instructions.lower()

    def test_verification_instructions_includes_trigger(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """Verification instructions include a trigger question example."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            result = agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        instructions = result["verification_instructions"]
        # Should reference asking a question or using the skill
        assert "ask" in instructions.lower() or "claude" in instructions.lower()

    def test_verification_instructions_lists_output_files(
        self,
        tmp_path: Path,
        brief: SkillBrief,
        skill_draft: dict[str, Any],
        setup_draft: dict[str, Any],
    ) -> None:
        """Verification instructions list the output files."""
        agent = PackagerAgent()
        with patch(
            "skill_builder.agents.packager._resolve_deploy_path",
            return_value=tmp_path / "output",
        ):
            result = agent.run(skill_draft=skill_draft, setup_draft=setup_draft, brief=brief)

        instructions = result["verification_instructions"]
        assert "SKILL.md" in instructions
        assert "SETUP.md" in instructions
