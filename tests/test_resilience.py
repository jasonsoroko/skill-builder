"""Tests for api_retry -- tenacity-based exponential backoff for API calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import httpx
import pytest
import requests
from firecrawl.v2.utils.error_handler import (
    InternalServerError as FirecrawlInternalServerError,
    RateLimitError as FirecrawlRateLimitError,
    RequestTimeoutError as FirecrawlRequestTimeoutError,
)
from tavily.errors import UsageLimitExceededError as TavilyUsageLimitError


class TestApiRetry:
    """api_retry decorator provides exponential backoff on transient errors."""

    def test_retries_on_rate_limit_error(self) -> None:
        """api_retry retries on RateLimitError with exponential backoff."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def flaky_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # RateLimitError requires a response-like object
                raise anthropic.RateLimitError(
                    message="Rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                )
            return "success"

        result = flaky_call()
        assert result == "success"
        assert call_count == 3

    def test_retries_on_api_connection_error(self) -> None:
        """api_retry retries on APIConnectionError."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def flaky_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise anthropic.APIConnectionError(request=MagicMock())
            return "success"

        result = flaky_call()
        assert result == "success"
        assert call_count == 3

    def test_does_not_retry_on_authentication_error(self) -> None:
        """api_retry does NOT retry on AuthenticationError (permanent error)."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def auth_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise anthropic.AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            )

        with pytest.raises(anthropic.AuthenticationError):
            auth_fail()

        assert call_count == 1  # No retry

    def test_does_not_retry_on_bad_request_error(self) -> None:
        """api_retry does NOT retry on BadRequestError (permanent error)."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def bad_request() -> str:
            nonlocal call_count
            call_count += 1
            raise anthropic.BadRequestError(
                message="Bad request",
                response=MagicMock(status_code=400, headers={}),
                body=None,
            )

        with pytest.raises(anthropic.BadRequestError):
            bad_request()

        assert call_count == 1  # No retry

    def test_stops_after_max_attempts(self) -> None:
        """api_retry stops retrying after max_attempts and reraises the error."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise anthropic.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )

        with pytest.raises(anthropic.RateLimitError):
            always_fails()

        assert call_count == 3  # Tried 3 times then gave up

    def test_retries_on_5xx_api_status_error(self) -> None:
        """api_retry retries on 5xx APIStatusError (server errors)."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def server_error() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise anthropic.APIStatusError(
                    message="Internal server error",
                    response=MagicMock(status_code=500, headers={}),
                    body=None,
                )
            return "success"

        result = server_error()
        assert result == "success"
        assert call_count == 3

    def test_does_not_retry_on_404_api_status_error(self) -> None:
        """api_retry does NOT retry on 404 APIStatusError (not a server error)."""
        from skill_builder.resilience import api_retry

        call_count = 0

        @api_retry(max_attempts=3)
        def not_found() -> str:
            nonlocal call_count
            call_count += 1
            raise anthropic.NotFoundError(
                message="Not found",
                response=MagicMock(status_code=404, headers={}),
                body=None,
            )

        with pytest.raises(anthropic.NotFoundError):
            not_found()

        assert call_count == 1  # No retry


class TestUnifiedRetry:
    """_is_retryable_any classifies transient errors from ALL external SDKs."""

    def test_retryable_firecrawl_rate_limit(self) -> None:
        """_is_retryable_any returns True for FirecrawlRateLimitError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(FirecrawlRateLimitError("rate limited")) is True

    def test_retryable_firecrawl_internal_server(self) -> None:
        """_is_retryable_any returns True for FirecrawlInternalServerError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(FirecrawlInternalServerError("server error")) is True

    def test_retryable_firecrawl_request_timeout(self) -> None:
        """_is_retryable_any returns True for FirecrawlRequestTimeoutError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(FirecrawlRequestTimeoutError("timeout")) is True

    def test_retryable_tavily_usage_limit(self) -> None:
        """_is_retryable_any returns True for TavilyUsageLimitError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(TavilyUsageLimitError("usage limit")) is True

    def test_retryable_requests_connection_error(self) -> None:
        """_is_retryable_any returns True for requests.ConnectionError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(requests.ConnectionError("connection failed")) is True

    def test_retryable_requests_timeout(self) -> None:
        """_is_retryable_any returns True for requests.Timeout."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(requests.Timeout("timed out")) is True

    def test_retryable_httpx_connect_error(self) -> None:
        """_is_retryable_any returns True for httpx.ConnectError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(httpx.ConnectError("connect failed")) is True

    def test_retryable_httpx_read_timeout(self) -> None:
        """_is_retryable_any returns True for httpx.ReadTimeout."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(httpx.ReadTimeout("read timed out")) is True

    def test_retryable_httpx_connect_timeout(self) -> None:
        """_is_retryable_any returns True for httpx.ConnectTimeout."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(httpx.ConnectTimeout("connect timed out")) is True

    def test_retryable_anthropic_rate_limit(self) -> None:
        """_is_retryable_any preserves existing Anthropic RateLimitError handling."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        assert _is_retryable_any(exc) is True

    def test_retryable_anthropic_connection_error(self) -> None:
        """_is_retryable_any preserves existing Anthropic APIConnectionError handling."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.APIConnectionError(request=MagicMock())
        assert _is_retryable_any(exc) is True

    def test_retryable_anthropic_5xx(self) -> None:
        """_is_retryable_any preserves existing Anthropic 5xx handling."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.APIStatusError(
            message="Server error",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        assert _is_retryable_any(exc) is True

    def test_not_retryable_anthropic_auth_error(self) -> None:
        """_is_retryable_any returns False for Anthropic AuthenticationError."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.AuthenticationError(
            message="Invalid key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        assert _is_retryable_any(exc) is False

    def test_not_retryable_anthropic_bad_request(self) -> None:
        """_is_retryable_any returns False for Anthropic BadRequestError."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.BadRequestError(
            message="Bad request",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        assert _is_retryable_any(exc) is False

    def test_not_retryable_anthropic_404(self) -> None:
        """_is_retryable_any returns False for Anthropic 404 NotFoundError."""
        from skill_builder.resilience import _is_retryable_any

        exc = anthropic.NotFoundError(
            message="Not found",
            response=MagicMock(status_code=404, headers={}),
            body=None,
        )
        assert _is_retryable_any(exc) is False

    def test_not_retryable_generic_value_error(self) -> None:
        """_is_retryable_any returns False for generic ValueError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(ValueError("bad value")) is False

    def test_not_retryable_generic_runtime_error(self) -> None:
        """_is_retryable_any returns False for generic RuntimeError."""
        from skill_builder.resilience import _is_retryable_any

        assert _is_retryable_any(RuntimeError("runtime fail")) is False

    def test_api_retry_any_retries_firecrawl_rate_limit(self) -> None:
        """api_retry_any decorator retries on FirecrawlRateLimitError then succeeds."""
        from skill_builder.resilience import api_retry_any

        call_count = 0

        @api_retry_any(max_attempts=3)
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FirecrawlRateLimitError("rate limited")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_api_retry_any_does_not_retry_auth_error(self) -> None:
        """api_retry_any does NOT retry on Anthropic AuthenticationError."""
        from skill_builder.resilience import api_retry_any

        call_count = 0

        @api_retry_any(max_attempts=3)
        def auth_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise anthropic.AuthenticationError(
                message="Invalid key",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            )

        with pytest.raises(anthropic.AuthenticationError):
            auth_fail()
        assert call_count == 1


class TestRetryVisibility:
    """Retry callback prints message to stdout (not just logger)."""

    def test_retry_callback_prints_to_stdout(self, capsys) -> None:
        """Retry callback message is visible via capsys matching expected pattern."""
        from skill_builder.resilience import api_retry_any

        call_count = 0

        @api_retry_any(max_attempts=3)
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FirecrawlRateLimitError("rate limited")
            return "ok"

        flaky()
        captured = capsys.readouterr()
        # Should contain retry message with attempt number
        assert "Retrying after" in captured.out
        assert "RateLimitError" in captured.out
        assert "(attempt 2)" in captured.out
