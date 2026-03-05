"""Tests for Pydantic data models.

Covers:
- SkillBrief validation (valid, missing fields, invalid URL types, defaults)
- PipelineState JSON round-trip with datetime and enum
- PipelinePhase enum string serialization
- Model module exports
- HarvestPage/HarvestResult source attribution and version tracking fields
- ContentItem, GeneratedQueries, SaturationResult new models
- ResearchCategory uses ContentItem
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from skill_builder.models.brief import SkillBrief
from skill_builder.models.harvest import HarvestPage, HarvestResult
from skill_builder.models.state import PipelinePhase, PipelineState
from skill_builder.models.synthesis import (
    CategorizedResearch,
    ContentItem,
    GeneratedQueries,
    ResearchCategory,
    SaturationResult,
)


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
            "ContentItem",
            "EvaluationDimension",
            "EvaluationResult",
            "GapReport",
            "GeneratedQueries",
            "HarvestPage",
            "HarvestResult",
            "KnowledgeModel",
            "PipelinePhase",
            "PipelineState",
            "ResearchCategory",
            "SaturationResult",
            "SeedUrl",
            "SetupDraft",
            "SkillBrief",
            "SkillDraft",
        ]
        for name in expected_exports:
            assert hasattr(models, name), f"models.__init__ missing export: {name}"


class TestHarvestPageExtensions:
    """Test HarvestPage source attribution and version tracking fields."""

    def test_harvest_page_new_optional_fields_default_none(self) -> None:
        """HarvestPage new optional fields default to None."""
        page = HarvestPage(
            url="https://example.com",
            title="Test",
            content="Hello",
            source_type="crawl",
        )
        assert page.source_url is None
        assert page.detected_version is None

    def test_harvest_page_with_new_fields_roundtrips_json(self) -> None:
        """HarvestPage with source_url and detected_version round-trips through JSON."""
        page = HarvestPage(
            url="https://example.com/docs",
            title="API Docs",
            content="Version 4.18 reference",
            source_type="crawl",
            source_url="https://example.com",
            detected_version="4.18.0",
        )
        json_str = page.model_dump_json()
        restored = HarvestPage.model_validate_json(json_str)
        assert restored.source_url == "https://example.com"
        assert restored.detected_version == "4.18.0"
        assert restored.url == "https://example.com/docs"


class TestHarvestResultExtensions:
    """Test HarvestResult warnings, version_conflicts, queries_used fields."""

    def test_harvest_result_new_fields_default_empty(self) -> None:
        """HarvestResult new fields default to empty lists."""
        result = HarvestResult()
        assert result.warnings == []
        assert result.version_conflicts == []
        assert result.queries_used == []

    def test_harvest_result_with_warnings_roundtrips_json(self) -> None:
        """HarvestResult with warnings and version_conflicts serializes/deserializes."""
        result = HarvestResult(
            pages=[],
            total_pages=0,
            warnings=["Version conflict: source A reports v1.2, source B reports v1.3"],
            version_conflicts=[
                {"source_url": "https://a.com", "version": "1.2", "url": "https://a.com/docs"},
                {"source_url": "https://b.com", "version": "1.3", "url": "https://b.com/docs"},
            ],
            queries_used=["exa best practices", "tavily error messages"],
        )
        json_str = result.model_dump_json()
        restored = HarvestResult.model_validate_json(json_str)
        assert len(restored.warnings) == 1
        assert len(restored.version_conflicts) == 2
        assert len(restored.queries_used) == 2
        assert restored.version_conflicts[0]["version"] == "1.2"


class TestContentItem:
    """Test the new ContentItem model."""

    def test_content_item_validates_text_and_source_url(self) -> None:
        """ContentItem requires text and source_url."""
        item = ContentItem(text="Some research content", source_url="https://example.com")
        assert item.text == "Some research content"
        assert item.source_url == "https://example.com"

    def test_content_item_missing_field_raises_error(self) -> None:
        """ContentItem missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ContentItem(text="Some content")  # type: ignore[call-arg]

    def test_content_item_roundtrips_json(self) -> None:
        """ContentItem round-trips through JSON serialization."""
        item = ContentItem(text="Test content", source_url="https://example.com/page")
        json_str = item.model_dump_json()
        restored = ContentItem.model_validate_json(json_str)
        assert restored.text == item.text
        assert restored.source_url == item.source_url


class TestResearchCategoryWithContentItem:
    """Test ResearchCategory now holds ContentItem list."""

    def test_research_category_holds_content_items(self) -> None:
        """ResearchCategory.content is a list of ContentItem objects."""
        cat = ResearchCategory(
            name="installation",
            content=[
                ContentItem(text="pip install exa-py", source_url="https://docs.exa.ai/"),
                ContentItem(text="pip install tavily-python", source_url="https://docs.tavily.com/"),
            ],
        )
        assert len(cat.content) == 2
        assert isinstance(cat.content[0], ContentItem)
        assert cat.content[0].source_url == "https://docs.exa.ai/"


class TestCategorizedResearchExtensions:
    """Test CategorizedResearch tools_covered field."""

    def test_categorized_research_has_tools_covered(self) -> None:
        """CategorizedResearch has tools_covered list field."""
        cr = CategorizedResearch(
            categories=[],
            source_count=5,
            tools_covered=["exa", "tavily", "firecrawl"],
        )
        assert cr.tools_covered == ["exa", "tavily", "firecrawl"]

    def test_categorized_research_tools_covered_defaults_empty(self) -> None:
        """CategorizedResearch.tools_covered defaults to empty list."""
        cr = CategorizedResearch()
        assert cr.tools_covered == []


class TestGeneratedQueries:
    """Test the new GeneratedQueries model."""

    def test_generated_queries_validates_both_lists(self) -> None:
        """GeneratedQueries requires exa_queries and tavily_queries."""
        gq = GeneratedQueries(
            exa_queries=["exa semantic search best practices"],
            tavily_queries=["tavily error messages gotchas"],
        )
        assert len(gq.exa_queries) == 1
        assert len(gq.tavily_queries) == 1

    def test_generated_queries_roundtrips_json(self) -> None:
        """GeneratedQueries round-trips through JSON serialization."""
        gq = GeneratedQueries(
            exa_queries=["query1", "query2"],
            tavily_queries=["query3", "query4"],
        )
        json_str = gq.model_dump_json()
        restored = GeneratedQueries.model_validate_json(json_str)
        assert restored.exa_queries == gq.exa_queries
        assert restored.tavily_queries == gq.tavily_queries


class TestSaturationResult:
    """Test the new SaturationResult model."""

    def test_saturation_result_validates_fields(self) -> None:
        """SaturationResult validates is_saturated and missing_capabilities."""
        sr = SaturationResult(
            is_saturated=False,
            missing_capabilities=["semantic search", "error handling"],
        )
        assert sr.is_saturated is False
        assert len(sr.missing_capabilities) == 2

    def test_saturation_result_missing_capabilities_defaults_empty(self) -> None:
        """SaturationResult.missing_capabilities defaults to empty list."""
        sr = SaturationResult(is_saturated=True)
        assert sr.missing_capabilities == []

    def test_saturation_result_roundtrips_json(self) -> None:
        """SaturationResult round-trips through JSON serialization."""
        sr = SaturationResult(
            is_saturated=False,
            missing_capabilities=["web crawling"],
        )
        json_str = sr.model_dump_json()
        restored = SaturationResult.model_validate_json(json_str)
        assert restored.is_saturated is False
        assert restored.missing_capabilities == ["web crawling"]
