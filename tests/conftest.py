"""Shared test fixtures for skill-builder tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_brief_dict() -> dict[str, Any]:
    """Return a valid skill brief as a dictionary."""
    return {
        "name": "exa-tavily-firecrawl",
        "description": (
            "A skill for deep research crawling using Exa semantic search, "
            "Tavily web search, and Firecrawl site crawling together"
        ),
        "seed_urls": [
            {"url": "https://docs.exa.ai/", "type": "docs"},
            {"url": "https://docs.tavily.com/", "type": "docs"},
            {"url": "https://docs.firecrawl.dev/", "type": "docs"},
            {"url": "https://github.com/mendableai/firecrawl", "type": "github"},
        ],
        "tool_category": "research",
        "scope": "Using Exa, Tavily, and Firecrawl together for comprehensive research crawling",
        "required_capabilities": [
            "semantic search with Exa",
            "web search with Tavily",
            "site crawling with Firecrawl",
            "parallel execution",
            "result deduplication",
        ],
        "deploy_target": "user",
    }


@pytest.fixture
def sample_brief_json(sample_brief_dict: dict[str, Any]) -> str:
    """Return a valid skill brief as a JSON string."""
    return json.dumps(sample_brief_dict)


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Create and return a temporary state directory."""
    state_dir = tmp_path / ".skill-builder" / "state"
    state_dir.mkdir(parents=True)
    return state_dir
