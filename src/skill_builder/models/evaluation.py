"""Evaluation phase data models.

These models represent the output of the validation evaluators:
dimension scores and overall pass/fail results.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationDimension(BaseModel):
    """A single evaluation dimension with score and feedback."""

    name: str = Field(description="Dimension name (e.g., api_accuracy, completeness)")
    score: int = Field(ge=1, le=10, description="Score from 1-10")
    feedback: str = Field(description="Evaluator feedback for this dimension")
    passed: bool = Field(description="Whether this dimension passed (score >= 7)")


class EvaluationResult(BaseModel):
    """Aggregated evaluation result from all evaluators."""

    dimensions: list[EvaluationDimension] = Field(
        default_factory=list, description="Scores for each evaluation dimension"
    )
    overall_pass: bool = Field(description="Whether all dimensions passed")
    iteration: int = Field(description="Which validation iteration this is (1-based)")
