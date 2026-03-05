"""Tests for the harvest deduplication module.

Covers:
- normalize_url with trailing slashes, mixed case, query params, fragments
- content_hash produces consistent SHA-256
- deduplicate removes URL duplicates, content hash duplicates, preserves unique
- Empty input
"""

from __future__ import annotations

from skill_builder.harvest.dedup import content_hash, deduplicate, normalize_url
from skill_builder.models.harvest import HarvestPage


class TestNormalizeUrl:
    """Test URL normalization for dedup comparison."""

    def test_strips_trailing_slash(self) -> None:
        """normalize_url strips trailing slash from path."""
        assert normalize_url("https://example.com/docs/") == normalize_url(
            "https://example.com/docs"
        )

    def test_lowercases_scheme_and_host(self) -> None:
        """normalize_url lowercases scheme and host."""
        assert normalize_url("HTTPS://EXAMPLE.COM/docs") == normalize_url(
            "https://example.com/docs"
        )

    def test_sorts_query_params(self) -> None:
        """normalize_url sorts query parameters alphabetically."""
        url1 = "https://example.com/search?b=2&a=1"
        url2 = "https://example.com/search?a=1&b=2"
        assert normalize_url(url1) == normalize_url(url2)

    def test_strips_fragment(self) -> None:
        """normalize_url strips URL fragment."""
        assert normalize_url("https://example.com/page#section") == normalize_url(
            "https://example.com/page"
        )

    def test_root_path_preserved(self) -> None:
        """normalize_url preserves root path /."""
        result = normalize_url("https://example.com")
        assert "example.com" in result

    def test_different_paths_remain_different(self) -> None:
        """normalize_url keeps different paths distinct."""
        assert normalize_url("https://example.com/a") != normalize_url(
            "https://example.com/b"
        )


class TestContentHash:
    """Test content hashing for dedup."""

    def test_consistent_hash(self) -> None:
        """content_hash produces same hash for same content."""
        h1 = content_hash("Hello world")
        h2 = content_hash("Hello world")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        """content_hash produces different hashes for different content."""
        h1 = content_hash("Hello world")
        h2 = content_hash("Goodbye world")
        assert h1 != h2

    def test_whitespace_normalized(self) -> None:
        """content_hash normalizes whitespace before hashing."""
        h1 = content_hash("Hello   world")
        h2 = content_hash("Hello world")
        assert h1 == h2

    def test_tabs_and_newlines_normalized(self) -> None:
        """content_hash normalizes tabs and newlines."""
        h1 = content_hash("Hello\n\tworld")
        h2 = content_hash("Hello world")
        assert h1 == h2

    def test_hash_is_hex_string(self) -> None:
        """content_hash returns a hex string (SHA-256)."""
        h = content_hash("test")
        assert len(h) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in h)


class TestDeduplicate:
    """Test the deduplication function."""

    def _make_page(
        self, url: str, content: str, title: str = "Test"
    ) -> HarvestPage:
        return HarvestPage(
            url=url, title=title, content=content, source_type="crawl"
        )

    def test_removes_url_duplicates(self) -> None:
        """deduplicate removes pages with same normalized URL."""
        pages = [
            self._make_page("https://example.com/docs/", "Content A"),
            self._make_page("https://example.com/docs", "Content B"),
        ]
        result = deduplicate(pages)
        assert len(result) == 1
        assert result[0].content == "Content A"  # First wins

    def test_removes_content_hash_duplicates(self) -> None:
        """deduplicate removes pages with same content hash (different URLs)."""
        pages = [
            self._make_page("https://a.com/page1", "Same content here"),
            self._make_page("https://b.com/page2", "Same content here"),
        ]
        result = deduplicate(pages)
        assert len(result) == 1

    def test_preserves_unique_pages(self) -> None:
        """deduplicate preserves pages with different URLs and different content."""
        pages = [
            self._make_page("https://a.com/page1", "Content A"),
            self._make_page("https://b.com/page2", "Content B"),
            self._make_page("https://c.com/page3", "Content C"),
        ]
        result = deduplicate(pages)
        assert len(result) == 3

    def test_sets_content_hash_on_returned_pages(self) -> None:
        """deduplicate sets content_hash on all returned pages."""
        pages = [
            self._make_page("https://a.com", "Content A"),
            self._make_page("https://b.com", "Content B"),
        ]
        result = deduplicate(pages)
        for page in result:
            assert page.content_hash is not None
            assert len(page.content_hash) == 64

    def test_empty_input(self) -> None:
        """deduplicate returns empty list for empty input."""
        result = deduplicate([])
        assert result == []

    def test_case_insensitive_url_dedup(self) -> None:
        """deduplicate treats URLs case-insensitively for scheme and host."""
        pages = [
            self._make_page("HTTPS://EXAMPLE.COM/docs", "Content A"),
            self._make_page("https://example.com/docs", "Content B"),
        ]
        result = deduplicate(pages)
        assert len(result) == 1
