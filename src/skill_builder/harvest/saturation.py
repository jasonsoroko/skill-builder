"""Lightweight saturation pre-filter.

Makes a single cheap Sonnet call to check if harvested content covers
all required capabilities. This is a pre-filter -- the Gap Analyzer
is the real quality gate. Fails open on errors (returns saturated=True).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from skill_builder.models.harvest import HarvestPage
from skill_builder.models.synthesis import SaturationResult
from skill_builder.resilience import retry_parse

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Truncate content summaries to keep the prompt cheap
_MAX_CONTENT_CHARS = 500
_MAX_PAGES_IN_PROMPT = 20


async def check_saturation(
    client: Anthropic,
    pages: list[HarvestPage],
    required_capabilities: list[str],
) -> SaturationResult:
    """Check if harvested content covers all required capabilities.

    Uses a single cheap Sonnet call to quickly identify any required
    capability with zero representation in the harvested content.

    Per locked decision: lightweight pre-filter -- a single short Sonnet
    call, not a full analysis. The Gap Analyzer is the real quality gate.

    Fails open on error (returns is_saturated=True) so the pipeline
    continues even if this check fails.

    Args:
        client: Anthropic client instance.
        pages: Harvested pages to check.
        required_capabilities: List of capabilities that must be covered.

    Returns:
        SaturationResult with coverage assessment.
    """
    logger.info(
        "Saturation check: %d pages, %d required capabilities",
        len(pages),
        len(required_capabilities),
    )

    # Build a concise content summary
    content_summary_parts: list[str] = []
    for page in pages[:_MAX_PAGES_IN_PROMPT]:
        truncated = page.content[:_MAX_CONTENT_CHARS]
        content_summary_parts.append(f"- [{page.source_type}] {page.title}: {truncated}")
    content_summary = "\n".join(content_summary_parts) if content_summary_parts else "(no content)"

    capabilities_list = "\n".join(f"- {cap}" for cap in required_capabilities)

    prompt = f"""Check if the harvested content covers all required capabilities.

Required capabilities:
{capabilities_list}

Harvested content summary ({len(pages)} pages total):
{content_summary}

For each required capability, determine if there is at least some relevant content.
List any capabilities with zero representation in the harvested content.
If all capabilities have at least some coverage, set is_saturated=true."""

    try:
        response = retry_parse(
            client,
            model="claude-sonnet-4-6",
            max_tokens=1024,
            output_format=SaturationResult,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.parsed_output
        result._usage_meta = {  # type: ignore[attr-defined]
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        logger.info(
            "Saturation check result: saturated=%s, missing=%s",
            result.is_saturated,
            result.missing_capabilities,
        )
        return result
    except Exception:
        logger.warning(
            "Saturation check LLM call failed; failing open (assuming saturated)",
            exc_info=True,
        )
        return SaturationResult(is_saturated=True, missing_capabilities=[])
