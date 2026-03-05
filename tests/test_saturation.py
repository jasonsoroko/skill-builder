"""Tests for the saturation pre-filter check.

Covers:
- check_saturation returns SaturationResult for saturated case
- check_saturation detects missing capabilities
- LLM error fails open (returns saturated=True)
- Single cheap Sonnet call verification
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from skill_builder.models.harvest import HarvestPage
from skill_builder.models.synthesis import SaturationResult


def _make_pages(contents: list[str]) -> list[HarvestPage]:
    """Create mock HarvestPages with given contents."""
    return [
        HarvestPage(
            url=f"https://example.com/{i}",
            title=f"Page {i}",
            content=content,
            source_type="crawl",
        )
        for i, content in enumerate(contents)
    ]


def _make_mock_parse_response(result: SaturationResult) -> MagicMock:
    """Create a mock messages.parse() response."""
    response = MagicMock()
    response.parsed_output = result
    return response


class TestCheckSaturation:
    """Test check_saturation function."""

    @pytest.mark.asyncio
    async def test_returns_saturated_when_all_capabilities_covered(self) -> None:
        """check_saturation returns is_saturated=True when all capabilities present."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Content about auth", "Content about caching"])
        capabilities = ["authentication", "caching"]

        sat_result = SaturationResult(is_saturated=True, missing_capabilities=[])
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        result = await check_saturation(mock_client, pages, capabilities)

        assert result.is_saturated is True
        assert result.missing_capabilities == []

    @pytest.mark.asyncio
    async def test_detects_missing_capabilities(self) -> None:
        """check_saturation returns missing capabilities when some have no content."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Content about auth only"])
        capabilities = ["authentication", "caching", "logging"]

        sat_result = SaturationResult(
            is_saturated=False,
            missing_capabilities=["caching", "logging"],
        )
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        result = await check_saturation(mock_client, pages, capabilities)

        assert result.is_saturated is False
        assert "caching" in result.missing_capabilities
        assert "logging" in result.missing_capabilities

    @pytest.mark.asyncio
    async def test_llm_error_fails_open(self) -> None:
        """check_saturation returns saturated=True when LLM call fails."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Some content"])
        capabilities = ["authentication"]

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(side_effect=Exception("LLM error"))

        result = await check_saturation(mock_client, pages, capabilities)

        assert result.is_saturated is True
        assert result.missing_capabilities == []

    @pytest.mark.asyncio
    async def test_uses_sonnet_model(self) -> None:
        """check_saturation uses claude-sonnet-4-6 model."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Content"])
        capabilities = ["auth"]

        sat_result = SaturationResult(is_saturated=True, missing_capabilities=[])
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        await check_saturation(mock_client, pages, capabilities)

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_uses_small_max_tokens(self) -> None:
        """check_saturation uses max_tokens=1024 (cheap check)."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Content"])
        capabilities = ["auth"]

        sat_result = SaturationResult(is_saturated=True, missing_capabilities=[])
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        await check_saturation(mock_client, pages, capabilities)

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_uses_saturation_result_output_format(self) -> None:
        """check_saturation passes SaturationResult as output_format."""
        from skill_builder.harvest.saturation import check_saturation

        pages = _make_pages(["Content"])
        capabilities = ["auth"]

        sat_result = SaturationResult(is_saturated=True, missing_capabilities=[])
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        await check_saturation(mock_client, pages, capabilities)

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["output_format"] is SaturationResult

    @pytest.mark.asyncio
    async def test_handles_empty_pages(self) -> None:
        """check_saturation handles empty pages list."""
        from skill_builder.harvest.saturation import check_saturation

        sat_result = SaturationResult(
            is_saturated=False,
            missing_capabilities=["auth"],
        )
        mock_response = _make_mock_parse_response(sat_result)

        mock_client = MagicMock()
        mock_client.messages.parse = MagicMock(return_value=mock_response)

        result = await check_saturation(mock_client, [], ["auth"])

        assert result.is_saturated is False
