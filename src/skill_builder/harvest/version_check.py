"""Version detection and conflict flagging for harvested content.

Detects semver-like version numbers in text and compares them across
pages to identify disagreements and mismatches with a target version.
"""

from __future__ import annotations

import re

from skill_builder.models.harvest import HarvestPage

# Match semver-like patterns: v1.2.3, 4.18.0, 2.7, etc.
# Optionally prefixed with 'v' or 'V'. Captures the numeric portion.
_VERSION_PATTERN = re.compile(r"(?:^|(?<=\s)|(?<=v)|(?<=V))(\d+\.\d+(?:\.\d+)?)\b")


def detect_version(text: str) -> list[str]:
    """Extract unique version numbers from text.

    Finds semver-like patterns (e.g., v1.2.3, 4.18.0, 2.7) and returns
    a deduplicated list of version strings (without the 'v' prefix).

    Args:
        text: Text to search for version numbers.

    Returns:
        List of unique version strings found, in order of first appearance.
    """
    matches = _VERSION_PATTERN.findall(text)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)
    return unique


def check_version_conflicts(
    pages: list[HarvestPage],
    target_version: str | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Compare detected versions across pages and flag conflicts.

    For each page, detects version numbers. If multiple distinct versions are
    found across all pages, returns conflict dicts and warning messages.

    When target_version is set, also flags pages whose versions don't match.

    Args:
        pages: List of HarvestPage objects to check.
        target_version: Optional target version to compare against.

    Returns:
        Tuple of (conflicts_list, warnings_list).
        Each conflict dict: {"source_url": str, "version": str, "url": str}.
        Warnings: human-readable conflict descriptions.
    """
    # Collect all page-version pairs
    page_versions: list[tuple[HarvestPage, list[str]]] = []
    all_versions: set[str] = set()

    for page in pages:
        versions = detect_version(page.content)
        if versions:
            page_versions.append((page, versions))
            all_versions.update(versions)

    conflicts: list[dict[str, str]] = []
    warnings: list[str] = []

    # Only flag conflicts if there are multiple distinct versions across pages
    if len(all_versions) > 1 and len(page_versions) > 1:
        for page, versions in page_versions:
            for version in versions:
                conflicts.append({
                    "source_url": page.source_url or page.url,
                    "version": version,
                    "url": page.url,
                })

        # Generate a summary warning
        version_list = sorted(all_versions)
        warnings.append(
            f"Version conflict: sources report different versions: {', '.join(version_list)}"
        )

    # Check against target version if provided
    if target_version:
        for page, versions in page_versions:
            for version in versions:
                if version != target_version:
                    warnings.append(
                        f"Version mismatch: {page.url} reports {version}, "
                        f"target is {target_version}"
                    )

    return conflicts, warnings
