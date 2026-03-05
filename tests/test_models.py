"""Tests for Pydantic data models.

Covers:
- SkillBrief validation (valid, missing fields, invalid URL types, defaults)
- PipelineState JSON round-trip with datetime and enum
- PipelinePhase enum string serialization
- Model module exports
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from skill_builder.models.brief import SkillBrief
from skill_builder.models.state import PipelinePhase, PipelineState


class TestSkillBrief:
    """Test the SkillBrief Pydantic model."""

    def test_valid_brief_loads(self, sample_brief_json: str) -> None:
        """Valid SkillBrief JSON with all required fields loads successfully."""
        brief = SkillBrief.model_validate_json(sample_brief_json)
        assert brief.name == "exa-tavily-firecrawl"
        assert len(brief.seed_urls) == 4
        assert brief.tool_category == "research"
        assert brief.deploy_target == "user"
        assert len(brief.required_capabilities) == 5

    def test_missing_required_field_raises_error(self, sample_brief_dict: dict[str, Any]) -> None:
        """SkillBrief with missing required field raises ValidationError with field name."""
        del sample_brief_dict["name"]
        with pytest.raises(ValidationError) as exc_info:
            SkillBrief.model_validate(sample_brief_dict)
        assert "name" in str(exc_info.value)

    def test_invalid_url_type_raises_error(self, sample_brief_dict: dict[str, Any]) -> None:
        """SkillBrief with invalid URL type raises ValidationError."""
        sample_brief_dict["seed_urls"] = [
            {"url": "https://example.com", "type": "invalid_type"}
        ]
        with pytest.raises(ValidationError):
            SkillBrief.model_validate(sample_brief_dict)

    def test_optional_fields_have_defaults(self, sample_brief_dict: dict[str, Any]) -> None:
        """SkillBrief optional fields get sensible defaults when omitted."""
        # sample_brief_dict does not include target_api_version or max_pages
        brief = SkillBrief.model_validate(sample_brief_dict)
        assert brief.target_api_version is None
        assert brief.max_pages == 50

    def test_brief_name_derived(self, sample_brief_json: str) -> None:
        """SkillBrief derives a slugified brief_name from the name field."""
        brief = SkillBrief.model_validate_json(sample_brief_json)
        assert brief.brief_name == "exa-tavily-firecrawl"

    def test_empty_name_rejected(self, sample_brief_dict: dict[str, Any]) -> None:
        """SkillBrief rejects empty name string."""
        sample_brief_dict["name"] = ""
        with pytest.raises(ValidationError):
            SkillBrief.model_validate(sample_brief_dict)

    def test_empty_seed_urls_rejected(self, sample_brief_dict: dict[str, Any]) -> None:
        """SkillBrief rejects empty seed_urls list."""
        sample_brief_dict["seed_urls"] = []
        with pytest.raises(ValidationError):
            SkillBrief.model_validate(sample_brief_dict)

    def test_empty_required_capabilities_rejected(
        self, sample_brief_dict: dict[str, Any]
    ) -> None:
        """SkillBrief rejects empty required_capabilities list."""
        sample_brief_dict["required_capabilities"] = []
        with pytest.raises(ValidationError):
            SkillBrief.model_validate(sample_brief_dict)


class TestPipelineState:
    """Test the PipelineState model."""

    def test_state_json_roundtrip(self) -> None:
        """PipelineState round-trips through model_dump_json/model_validate_json."""
        state = PipelineState(brief_name="test-skill")
        json_str = state.model_dump_json()
        restored = PipelineState.model_validate_json(json_str)
        assert restored.brief_name == state.brief_name
        assert restored.phase == state.phase
        assert restored.started_at == state.started_at
        assert restored.updated_at == state.updated_at
        assert restored.gap_loop_count == 0
        assert restored.validation_loop_count == 0

    def test_state_preserves_enum_in_json(self) -> None:
        """PipelineState preserves PipelinePhase enum through JSON serialization."""
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.HARVESTING,
        )
        json_str = state.model_dump_json()
        data = json.loads(json_str)
        assert data["phase"] == "harvesting"
        restored = PipelineState.model_validate_json(json_str)
        assert restored.phase == PipelinePhase.HARVESTING

    def test_state_preserves_datetime_in_json(self) -> None:
        """PipelineState preserves datetime fields through JSON serialization."""
        state = PipelineState(brief_name="test-skill")
        json_str = state.model_dump_json()
        restored = PipelineState.model_validate_json(json_str)
        assert restored.started_at == state.started_at
        assert restored.updated_at == state.updated_at


class TestPipelinePhase:
    """Test the PipelinePhase enum."""

    def test_phase_values_are_strings(self) -> None:
        """PipelinePhase enum values are strings (str mixin)."""
        for phase in PipelinePhase:
            assert isinstance(phase.value, str)
            assert isinstance(phase, str)

    def test_phase_json_serializable(self) -> None:
        """PipelinePhase enum values are JSON-serializable."""
        for phase in PipelinePhase:
            serialized = json.dumps(phase.value)
            assert json.loads(serialized) == phase.value

    def test_all_expected_phases_exist(self) -> None:
        """All expected pipeline phases are defined."""
        expected = {
            "initialized",
            "intake",
            "harvesting",
            "organizing",
            "gap_analyzing",
            "re_harvesting",
            "learning",
            "mapping",
            "documenting",
            "validating",
            "re_producing",
            "packaging",
            "complete",
            "failed",
        }
        actual = {phase.value for phase in PipelinePhase}
        assert actual == expected


class TestModelExports:
    """Test that all model modules export their primary models."""

    def test_harvest_exports(self) -> None:
        """Harvest module exports HarvestPage and HarvestResult."""
        from skill_builder.models.harvest import HarvestPage, HarvestResult

        assert HarvestPage is not None
        assert HarvestResult is not None

    def test_synthesis_exports(self) -> None:
        """Synthesis module exports its primary models."""
        from skill_builder.models.synthesis import (
            CategorizedResearch,
            GapReport,
            KnowledgeModel,
            ResearchCategory,
        )

        assert ResearchCategory is not None
        assert CategorizedResearch is not None
        assert GapReport is not None
        assert KnowledgeModel is not None

    def test_production_exports(self) -> None:
        """Production module exports SkillDraft and SetupDraft."""
        from skill_builder.models.production import SetupDraft, SkillDraft

        assert SkillDraft is not None
        assert SetupDraft is not None

    def test_evaluation_exports(self) -> None:
        """Evaluation module exports EvaluationDimension and EvaluationResult."""
        from skill_builder.models.evaluation import EvaluationDimension, EvaluationResult

        assert EvaluationDimension is not None
        assert EvaluationResult is not None

    def test_models_init_reexports(self) -> None:
        """Models __init__ re-exports all primary models."""
        import skill_builder.models as models

        expected_exports = [
            "CategorizedResearch",
            "EvaluationDimension",
            "EvaluationResult",
            "GapReport",
            "HarvestPage",
            "HarvestResult",
            "KnowledgeModel",
            "PipelinePhase",
            "PipelineState",
            "ResearchCategory",
            "SeedUrl",
            "SetupDraft",
            "SkillBrief",
            "SkillDraft",
        ]
        for name in expected_exports:
            assert hasattr(models, name), f"models.__init__ missing export: {name}"
