"""PackagerAgent -- assembles and deploys the final .skill output.

The packager is the final pipeline step. It takes validated drafts (SkillDraft,
SetupDraft) and assembles a deployable output folder with SKILL.md, SETUP.md,
reference files, LICENSE.txt, and standard subdirectories.

No LLM calls -- pure Python file operations.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from skill_builder.models.brief import SkillBrief


def _resolve_deploy_path(deploy_target: str, tool_name: str) -> Path:
    """Resolve the output path based on deploy target.

    Args:
        deploy_target: One of "repo", "user", "package".
        tool_name: The slugified skill name (brief_name).

    Returns:
        Path to the output directory.

    Raises:
        ValueError: If deploy_target is not recognized.
    """
    if deploy_target == "repo":
        return Path(".claude/skills") / tool_name
    if deploy_target == "user":
        return Path.home() / ".claude" / "skills" / tool_name
    if deploy_target == "package":
        return Path(".skill-builder/output") / tool_name
    raise ValueError(f"Unknown deploy target: {deploy_target!r}. Expected 'repo', 'user', or 'package'.")


_MIT_LICENSE_TEMPLATE = """MIT License

Copyright (c) {year} {name}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


class PackagerAgent:
    """Assembles and deploys the final skill output folder.

    Conforms to BaseAgent Protocol: run(**kwargs) -> dict[str, Any].
    No LLM calls -- pure Python file operations.
    """

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Assemble output folder with skill files.

        Expected kwargs:
            skill_draft: dict with content, line_count, has_frontmatter, reference_files
            setup_draft: dict with content, has_prerequisites, has_quick_start
            brief: SkillBrief instance

        Returns:
            Dict with package_path (str) and verification_instructions (str).
        """
        skill_draft: dict[str, Any] = kwargs["skill_draft"]
        setup_draft: dict[str, Any] = kwargs["setup_draft"]
        brief: SkillBrief = kwargs["brief"]

        # Resolve output path
        output_path = _resolve_deploy_path(brief.deploy_target, brief.brief_name)

        # Create output directory
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise PermissionError(
                f"Cannot create output directory at {output_path}. "
                f"Check permissions for the deploy target '{brief.deploy_target}'. "
                f"Original error: {exc}"
            ) from exc

        # Write SKILL.md
        (output_path / "SKILL.md").write_text(skill_draft["content"])

        # Write SETUP.md
        (output_path / "SETUP.md").write_text(setup_draft["content"])

        # Create subdirectories
        for subdir in ("references", "scripts", "assets"):
            (output_path / subdir).mkdir(exist_ok=True)

        # Write reference files if present
        reference_files = skill_draft.get("reference_files")
        if reference_files:
            refs_dir = output_path / "references"
            for filename, content in reference_files.items():
                (refs_dir / filename).write_text(content)

        # Write LICENSE.txt
        year = datetime.datetime.now(datetime.UTC).year
        license_text = _MIT_LICENSE_TEMPLATE.format(year=year, name=brief.brief_name)
        (output_path / "LICENSE.txt").write_text(license_text)

        # Build verification instructions
        output_files = self._list_output_files(output_path)
        verification_instructions = self._build_verification_instructions(
            brief.name, output_path, output_files
        )

        return {
            "package_path": str(output_path),
            "verification_instructions": verification_instructions,
        }

    def _list_output_files(self, output_path: Path) -> list[tuple[str, int]]:
        """List all files in the output directory with line counts."""
        files: list[tuple[str, int]] = []
        for path in sorted(output_path.rglob("*")):
            if path.is_file():
                try:
                    line_count = len(path.read_text().splitlines())
                except (UnicodeDecodeError, PermissionError):
                    line_count = 0
                rel = path.relative_to(output_path)
                files.append((str(rel), line_count))
        return files

    def _build_verification_instructions(
        self, skill_name: str, output_path: Path, output_files: list[tuple[str, int]]
    ) -> str:
        """Build human-readable verification instructions."""
        file_list = "\n".join(
            f"  - {name} ({lines} lines)" for name, lines in output_files
        )
        return (
            f"To verify the skill works:\n"
            f"1. Open Claude Code in a project\n"
            f"2. Ask: 'Help me use {skill_name}'\n"
            f"3. Check that the skill activates and provides accurate guidance\n"
            f"\n"
            f"Output files:\n"
            f"{file_list}"
        )
