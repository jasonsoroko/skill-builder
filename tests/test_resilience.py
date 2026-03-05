"""Tests for api_retry -- tenacity-based exponential backoff for API calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import pytest


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
