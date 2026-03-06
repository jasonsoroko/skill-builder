"""Resilience patterns -- tenacity retry decorator for external API calls.

Provides exponential backoff with jitter for transient API errors.
Retries on RateLimitError, APIConnectionError, and 5xx server errors.
Does NOT retry on permanent errors (AuthenticationError, BadRequestError, etc.).

The unified `_is_retryable_any` classifier and `api_retry_any` decorator extend
coverage to all external SDKs: Firecrawl, Exa (via requests), Tavily, and
GitHub (via httpx), in addition to Anthropic.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
import httpx
import requests
from firecrawl.v2.utils.error_handler import (
    FirecrawlError,
    InternalServerError as FirecrawlInternalServerError,
    RateLimitError as FirecrawlRateLimitError,
    RequestTimeoutError as FirecrawlRequestTimeoutError,
)
from tavily.errors import UsageLimitExceededError as TavilyUsageLimitError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Determine whether an exception is retryable (Anthropic-only).

    Retryable:
    - RateLimitError (429)
    - APIConnectionError (network issues)
    - APIStatusError with 5xx status code (server errors)

    Not retryable:
    - AuthenticationError (401)
    - BadRequestError (400)
    - NotFoundError (404)
    - Any other non-5xx APIStatusError
    """
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return False


def _is_retryable_any(exc: BaseException) -> bool:
    """Classify transient errors from ALL external SDKs.

    Covers: Anthropic, Firecrawl, Tavily, requests (Exa/Tavily), httpx (GitHub).
    Returns True for transient/retryable errors, False for permanent errors.
    """
    # Anthropic (existing logic preserved)
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500

    # Firecrawl
    if isinstance(exc, (FirecrawlRateLimitError, FirecrawlInternalServerError, FirecrawlRequestTimeoutError)):
        return True

    # Tavily
    if isinstance(exc, TavilyUsageLimitError):
        return True

    # Generic network errors from requests (used by Exa and Tavily SDKs)
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True

    # httpx errors (used by Firecrawl async and GitHub strategy)
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return True

    return False


def _make_retry_callback():
    """Create a before_sleep callback that prints retry messages to CLI.

    Per locked decision: retry attempts must be visible in normal CLI output,
    not just --verbose mode. Uses print() for user visibility plus logger.warning()
    for structured logging.
    """
    def callback(retry_state):
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        exc_name = type(exc).__name__ if exc else "unknown"
        attempt = retry_state.attempt_number + 1
        msg = f"  Retrying after {exc_name} (attempt {attempt})..."
        logger.warning(msg)
        print(msg)
    return callback


def api_retry(max_attempts: int = 5) -> Any:
    """Retry decorator for Anthropic API calls with exponential backoff + jitter.

    Usage:
        @api_retry(max_attempts=5)
        def call_anthropic():
            ...
    """
    return retry(
        wait=wait_exponential_jitter(initial=0.01, max=0.1, jitter=0.01),
        stop=stop_after_attempt(max_attempts),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            "Retry attempt %d after %s: %s",
            retry_state.attempt_number,
            type(retry_state.outcome.exception()).__name__ if retry_state.outcome else "unknown",
            retry_state.outcome.exception() if retry_state.outcome else "unknown",
        ),
    )


def api_retry_any(
    max_attempts: int = 5, *, initial: float = 1.0, max_wait: float = 60.0
) -> Any:
    """Retry decorator for ALL external API calls with exponential backoff + jitter.

    Covers all SDKs: Anthropic, Firecrawl, Exa (requests), Tavily, GitHub (httpx).
    Uses _is_retryable_any for classification and _make_retry_callback for
    user-visible retry messages.

    Args:
        max_attempts: Maximum number of retry attempts.
        initial: Initial backoff delay in seconds (default 1.0 for production).
        max_wait: Maximum backoff delay in seconds (default 60.0 for production).

    Usage:
        @api_retry_any(max_attempts=5)
        def call_any_api():
            ...
    """
    return retry(
        wait=wait_exponential_jitter(initial=initial, max=max_wait, jitter=initial),
        stop=stop_after_attempt(max_attempts),
        retry=retry_if_exception(_is_retryable_any),
        reraise=True,
        before_sleep=_make_retry_callback(),
    )


_parse_retry = api_retry_any()


def retry_parse(client: Any, **kwargs: Any) -> Any:
    """Call client.messages.parse with retry on transient errors.

    Wraps the call in a shared api_retry_any instance with production timings.
    """
    return _parse_retry(lambda: client.messages.parse(**kwargs))()
