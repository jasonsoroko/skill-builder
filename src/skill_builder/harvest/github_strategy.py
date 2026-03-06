"""GitHub REST API content extraction strategy.

Extracts README, docs/ directory, and examples/ directory from GitHub repos.
Follows internal links from README one level deep. Auto-discovers published
docs site URLs from README content (GitHub Pages, ReadTheDocs patterns).
"""

from __future__ import annotations

import logging
import os
import re

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from skill_builder.models.harvest import HarvestPage
from skill_builder.resilience import _is_retryable_any, _make_retry_callback

logger = logging.getLogger(__name__)


async def _httpx_get_with_retry(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Issue an httpx GET with exponential backoff retry on transient errors."""
    async for attempt in AsyncRetrying(
        wait=wait_exponential_jitter(initial=1.0, max=60.0, jitter=1.0),
        stop=stop_after_attempt(5),
        retry=retry_if_exception(_is_retryable_any),
        reraise=True,
        before_sleep=_make_retry_callback(),
    ):
        with attempt:
            return await client.get(url, **kwargs)

# Patterns for auto-discovering docs site URLs
_DOCS_URL_PATTERNS = [
    re.compile(r"https?://[\w.-]+\.github\.io[/\w.-]*"),
    re.compile(r"https?://[\w.-]+\.readthedocs\.io[/\w.-]*"),
    re.compile(r"https?://docs\.[\w.-]+[/\w.-]*"),
]

# File extensions to extract from docs/ and examples/ directories
_EXTRACTABLE_EXTENSIONS = (".md", ".rst", ".txt")

# Base API URL
_GITHUB_API = "https://api.github.com"


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """Parse owner and repo name from a GitHub URL.

    Handles trailing slashes, .git suffix, and various URL formats.
    """
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    # Find github.com in parts and take the next two
    for i, part in enumerate(parts):
        if "github.com" in part and i + 2 < len(parts):
            return parts[i + 1], parts[i + 2]
    # Fallback: take last two parts
    return parts[-2], parts[-1]


def _extract_relative_links(readme_content: str) -> list[str]:
    """Extract relative markdown links from README content.

    Returns paths that are relative to the repo root (not external URLs).
    """
    # Match markdown links: [text](path)
    link_pattern = re.compile(r"\[(?:[^\]]+)\]\(([^)]+)\)")
    links = []
    for match in link_pattern.finditer(readme_content):
        path = match.group(1)
        # Skip external URLs, anchors, and images
        if path.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # Strip any anchor from the path
        path = path.split("#")[0]
        if path and path.endswith((".md", ".rst", ".txt")):
            links.append(path)
    return links


def _discover_docs_urls(readme_content: str) -> list[str]:
    """Auto-discover published docs site URLs from README content."""
    discovered: list[str] = []
    for pattern in _DOCS_URL_PATTERNS:
        for match in pattern.finditer(readme_content):
            url = match.group(0)
            if url not in discovered:
                discovered.append(url)
    return discovered


async def github_extract(
    repo_url: str, *, max_pages: int = 50
) -> tuple[list[HarvestPage], list[str]]:
    """Extract docs content from a GitHub repo via REST API.

    Per locked decision: extract README, docs/ directory, and examples/
    directory only. Skip source code files. Follow internal links from
    README one level deep. Auto-discover published docs sites.

    Args:
        repo_url: GitHub repository URL.
        max_pages: Maximum pages to extract.

    Returns:
        Tuple of (pages, discovered_docs_urls).
        Pages are HarvestPage objects with source_type="github_api".
        discovered_docs_urls are docs site URLs found in README.
    """
    owner, repo = _parse_owner_repo(repo_url)
    logger.info("GitHub extract: %s/%s (max_pages=%d)", owner, repo, max_pages)

    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("GITHUB_TOKEN not set; using unauthenticated requests (60 req/hr limit)")

    pages: list[HarvestPage] = []
    discovered_docs_urls: list[str] = []

    async with httpx.AsyncClient(
        headers=headers, timeout=30.0, follow_redirects=True
    ) as client:
        # 1. Fetch README
        readme_content = ""
        resp = await _httpx_get_with_retry(client,
            f"{_GITHUB_API}/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if resp.status_code == 200:
            readme_content = resp.text
            pages.append(
                HarvestPage(
                    url=f"https://github.com/{owner}/{repo}#readme",
                    title=f"{repo} README",
                    content=readme_content,
                    source_type="github_api",
                    source_url=repo_url,
                )
            )
            # Auto-discover docs site URLs
            discovered_docs_urls = _discover_docs_urls(readme_content)
        else:
            logger.warning("Failed to fetch README for %s/%s: %d", owner, repo, resp.status_code)

        # 2. Fetch docs/ and examples/ directories
        for directory in ("docs", "examples"):
            if len(pages) >= max_pages:
                break
            resp = await _httpx_get_with_retry(
                client, f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{directory}"
            )
            if resp.status_code != 200:
                continue

            for item in resp.json():
                if len(pages) >= max_pages:
                    break
                if item.get("type") != "file":
                    continue
                name = item.get("name", "")
                if not name.endswith(_EXTRACTABLE_EXTENSIONS):
                    continue

                file_resp = await _httpx_get_with_retry(client,
                    item["url"],
                    headers={"Accept": "application/vnd.github.raw+json"},
                )
                if file_resp.status_code == 200:
                    pages.append(
                        HarvestPage(
                            url=item.get("html_url", item["url"]),
                            title=name,
                            content=file_resp.text,
                            source_type="github_api",
                            source_url=repo_url,
                        )
                    )

        # 3. Follow internal links from README one level deep
        if readme_content:
            relative_links = _extract_relative_links(readme_content)
            for link_path in relative_links:
                if len(pages) >= max_pages:
                    break
                # Normalize path (remove leading ./)
                clean_path = link_path.lstrip("./")
                resp = await _httpx_get_with_retry(client,
                    f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{clean_path}",
                    headers={"Accept": "application/vnd.github.raw+json"},
                )
                if resp.status_code == 200:
                    pages.append(
                        HarvestPage(
                            url=f"https://github.com/{owner}/{repo}/blob/main/{clean_path}",
                            title=clean_path.split("/")[-1],
                            content=resp.text,
                            source_type="github_api",
                            source_url=repo_url,
                        )
                    )

    logger.info(
        "GitHub extract: %s/%s returned %d pages, %d docs URLs",
        owner,
        repo,
        len(pages),
        len(discovered_docs_urls),
    )
    return pages, discovered_docs_urls
