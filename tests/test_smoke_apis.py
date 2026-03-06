"""Layer 0: API smoke tests -- verify all external API keys and SDK contracts.

Each test sends the smallest possible request to one external API.
Total cost: ~$0.01. Run with: pytest -m live --tb=short -v
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.live, pytest.mark.timeout(30)]


@pytest.fixture
def skip_if_no_key():
    """Helper to skip tests when API keys are missing."""

    def _check(env_var: str):
        if not os.environ.get(env_var):
            pytest.skip(f"{env_var} not set")

    return _check


class TestSmokeAPIs:
    """Verify each external API responds to a minimal request."""

    def test_anthropic_ping(self, skip_if_no_key) -> None:
        """Anthropic API responds with cheapest model (Haiku)."""
        skip_if_no_key("ANTHROPIC_API_KEY")
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
        assert response.content
        assert response.usage.input_tokens > 0

    def test_firecrawl_ping(self, skip_if_no_key) -> None:
        """Firecrawl API scrapes a single known URL."""
        skip_if_no_key("FIRECRAWL_API_KEY")
        from firecrawl import Firecrawl

        fc = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
        result = fc.scrape("https://example.com", formats=["markdown"])
        assert result.markdown
        assert len(result.markdown) > 0

    def test_exa_ping(self, skip_if_no_key) -> None:
        """Exa API returns a search result with expected attributes."""
        skip_if_no_key("EXA_API_KEY")
        from exa_py import Exa

        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        response = exa.search(
            "test query",
            num_results=1,
            type="auto",
            contents={"text": {"max_characters": 100}},
        )
        assert hasattr(response, "results")
        assert len(response.results) >= 1
        result = response.results[0]
        assert hasattr(result, "url")
        assert hasattr(result, "text")

    def test_tavily_ping(self, skip_if_no_key) -> None:
        """Tavily API returns a search result with expected dict structure."""
        skip_if_no_key("TAVILY_API_KEY")
        from tavily import TavilyClient

        tavily = TavilyClient()
        response = tavily.search("test query", max_results=1)
        assert "results" in response
        assert len(response["results"]) >= 1
        item = response["results"][0]
        assert "url" in item
        assert "content" in item

    @pytest.mark.asyncio
    async def test_github_ping(self) -> None:
        """GitHub API responds to an unauthenticated (or token-auth) GET."""
        import httpx

        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            resp = await client.get(
                "https://api.github.com/repos/anthropics/anthropic-sdk-python"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "full_name" in data
