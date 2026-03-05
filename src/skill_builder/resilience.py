"""Resilience patterns -- tenacity retry decorator for external API calls.

Provides exponential backoff with jitter for transient API errors.
Retries on RateLimitError, APIConnectionError, and 5xx server errors.
Does NOT retry on permanent errors (AuthenticationError, BadRequestError, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Determine whether an exception is retryable.

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


def api_retry(max_attempts: int = 5) -> Any:
    """Retry decorator for external API calls with exponential backoff + jitter.

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
