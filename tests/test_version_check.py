"""Tests for the harvest version detection module.

Covers:
- detect_version finds semver patterns (v1.2.3, 4.18.0, version 2.7)
- detect_version returns empty list for versionless text
- check_version_conflicts flags disagreements
- check_version_conflicts with target_version filters correctly
"""

from __future__ import annotations

from skill_builder.harvest.version_check import check_version_conflicts, detect_version
from skill_builder.models.harvest import HarvestPage


class TestDetectVersion:
    """Test version detection from text."""

    def test_finds_semver_v_prefix(self) -> None:
        """detect_version finds version with v prefix like v1.2.3."""
        versions = detect_version("This is v1.2.3 release")
        assert "1.2.3" in versions

    def test_finds_semver_no_prefix(self) -> None:
        """detect_version finds version without v prefix like 4.18.0."""
        versions = detect_version("Released version 4.18.0")
        assert "4.18.0" in versions

    def test_finds_two_part_version(self) -> None:
        """detect_version finds two-part version like 2.7."""
        versions = detect_version("Compatible with Python 2.7")
        assert "2.7" in versions

    def test_returns_empty_for_versionless_text(self) -> None:
        """detect_version returns empty list when no versions found."""
        versions = detect_version("This text has no version numbers at all")
        assert versions == []

    def test_returns_unique_versions(self) -> None:
        """detect_version returns unique versions even if repeated."""
        versions = detect_version("v1.2.3 is great. We love v1.2.3!")
        assert versions.count("1.2.3") == 1

    def test_finds_multiple_different_versions(self) -> None:
        """detect_version finds all distinct versions in text."""
        versions = detect_version("Upgrade from v1.0.0 to v2.0.0")
        assert "1.0.0" in versions
        assert "2.0.0" in versions


class TestCheckVersionConflicts:
    """Test version conflict checking across pages."""

    def _make_page(
        self, url: str, content: str, source_url: str | None = None
    ) -> HarvestPage:
        return HarvestPage(
            url=url,
            title="Test",
            content=content,
            source_type="crawl",
            source_url=source_url,
        )

    def test_no_conflicts_when_versions_agree(self) -> None:
        """check_version_conflicts returns no conflicts when all versions match."""
        pages = [
            self._make_page("https://a.com", "Version 4.18.0", "https://seed.com"),
            self._make_page("https://b.com", "Requires 4.18.0", "https://seed.com"),
        ]
        conflicts, warnings = check_version_conflicts(pages)
        assert len(conflicts) == 0
        assert len(warnings) == 0

    def test_flags_version_disagreements(self) -> None:
        """check_version_conflicts flags when sources report different versions."""
        pages = [
            self._make_page("https://a.com", "Uses v1.2.0"),
            self._make_page("https://b.com", "Requires v1.3.0"),
        ]
        conflicts, warnings = check_version_conflicts(pages)
        assert len(conflicts) >= 2  # One entry per page with a version
        assert len(warnings) >= 1  # At least one warning about the disagreement

    def test_target_version_mismatch_flagged(self) -> None:
        """check_version_conflicts flags pages with versions that don't match target."""
        pages = [
            self._make_page("https://a.com", "This is for v1.0.0"),
            self._make_page("https://b.com", "Updated to v2.0.0"),
        ]
        conflicts, warnings = check_version_conflicts(pages, target_version="2.0.0")
        # Should flag the v1.0.0 as a mismatch
        assert any("1.0.0" in str(w) for w in warnings)

    def test_no_versions_found_no_conflicts(self) -> None:
        """check_version_conflicts returns no conflicts for versionless pages."""
        pages = [
            self._make_page("https://a.com", "No version here"),
            self._make_page("https://b.com", "Also no version"),
        ]
        conflicts, warnings = check_version_conflicts(pages)
        assert len(conflicts) == 0
        assert len(warnings) == 0

    def test_single_page_no_conflict(self) -> None:
        """check_version_conflicts with one page never has conflicts."""
        pages = [self._make_page("https://a.com", "Version 3.14.0")]
        conflicts, warnings = check_version_conflicts(pages)
        assert len(conflicts) == 0
        assert len(warnings) == 0

    def test_conflict_dict_has_required_keys(self) -> None:
        """Each conflict dict has source_url, version, and url keys."""
        pages = [
            self._make_page("https://a.com", "v1.0.0", source_url="https://seed-a.com"),
            self._make_page("https://b.com", "v2.0.0", source_url="https://seed-b.com"),
        ]
        conflicts, _ = check_version_conflicts(pages)
        for conflict in conflicts:
            assert "source_url" in conflict
            assert "version" in conflict
            assert "url" in conflict
