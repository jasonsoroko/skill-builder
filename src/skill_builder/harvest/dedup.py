"""Content deduplication -- URL normalization and SHA-256 content hashing.

Removes duplicate pages by normalized URL and by content hash (same content
from different URLs). Sets `content_hash` on all returned pages.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse

from skill_builder.models.harvest import HarvestPage


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication comparison.

    - Lowercases scheme and host
    - Strips trailing slash from path
    - Sorts query parameters
    - Strips fragment
    """
    parsed = urlparse(url)
    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # Strip trailing slash from path (but keep "/" for root)
    path = parsed.path.rstrip("/") or "/"
    # Sort query params -- parse_qs returns dict[str, list[str]]
    query_dict = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_dict.items()), doseq=True)
    # Strip fragment
    normalized = f"{scheme}://{netloc}{path}"
    if sorted_query:
        normalized += f"?{sorted_query}"
    return normalized


def content_hash(content: str) -> str:
    """SHA-256 hash of whitespace-normalized content.

    Collapses all whitespace (spaces, tabs, newlines) into single spaces
    before hashing, so formatting differences don't create false negatives.
    """
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate(pages: list[HarvestPage]) -> list[HarvestPage]:
    """Remove duplicate pages by normalized URL or content hash.

    First-seen page wins for both URL and content deduplication.
    Sets `content_hash` on all returned pages.

    Args:
        pages: List of HarvestPage objects, possibly with duplicates.

    Returns:
        Deduplicated list with content_hash set on each page.
    """
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique: list[HarvestPage] = []

    for page in pages:
        norm_url = normalize_url(page.url)
        if norm_url in seen_urls:
            continue

        h = content_hash(page.content)
        if h in seen_hashes:
            continue

        # Use model_copy to set content_hash without mutating the original
        deduped_page = page.model_copy(update={"content_hash": h})
        seen_urls.add(norm_url)
        seen_hashes.add(h)
        unique.append(deduped_page)

    return unique
