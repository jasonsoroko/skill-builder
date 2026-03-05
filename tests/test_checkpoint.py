"""Tests for CheckpointStore -- JSON persistence of PipelineState."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_builder.models.state import PipelinePhase, PipelineState


class TestCheckpointStore:
    """CheckpointStore saves and loads PipelineState to/from JSON."""

    def test_save_creates_json_file(self, tmp_path: Path) -> None:
        """save() writes a JSON file named {brief_name}.json."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        state = PipelineState(brief_name="test-skill")
        store.save(state)

        assert (tmp_path / "state" / "test-skill.json").exists()

    def test_load_returns_valid_pipeline_state(self, tmp_path: Path) -> None:
        """load() returns a PipelineState with all fields preserved."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        state = PipelineState(
            brief_name="test-skill",
            phase=PipelinePhase.HARVESTING,
            total_input_tokens=1500,
            total_output_tokens=800,
            total_cost_usd=0.05,
            gap_loop_count=1,
        )
        store.save(state)
        loaded = store.load("test-skill")

        assert loaded is not None
        assert loaded.brief_name == "test-skill"
        assert loaded.phase == PipelinePhase.HARVESTING
        assert loaded.total_input_tokens == 1500
        assert loaded.total_output_tokens == 800
        assert loaded.total_cost_usd == 0.05
        assert loaded.gap_loop_count == 1

    def test_load_preserves_datetime_fields(self, tmp_path: Path) -> None:
        """load() preserves datetime fields (started_at, updated_at) through JSON round-trip."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        now = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)
        state = PipelineState(brief_name="test-skill", started_at=now, updated_at=now)
        store.save(state)
        loaded = store.load("test-skill")

        assert loaded is not None
        assert loaded.started_at.year == 2026
        assert loaded.started_at.month == 3

    def test_load_preserves_enum_phase(self, tmp_path: Path) -> None:
        """load() preserves PipelinePhase enum through JSON round-trip."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        state = PipelineState(brief_name="test-skill", phase=PipelinePhase.GAP_ANALYZING)
        store.save(state)
        loaded = store.load("test-skill")

        assert loaded is not None
        assert loaded.phase == PipelinePhase.GAP_ANALYZING
        assert isinstance(loaded.phase, PipelinePhase)

    def test_load_preserves_optional_none_fields(self, tmp_path: Path) -> None:
        """load() preserves None optional fields (raw_harvest, error, etc.)."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        state = PipelineState(brief_name="test-skill")
        store.save(state)
        loaded = store.load("test-skill")

        assert loaded is not None
        assert loaded.raw_harvest is None
        assert loaded.error is None
        assert loaded.evaluation_results == []

    def test_load_returns_none_for_nonexistent_brief(self, tmp_path: Path) -> None:
        """load() returns None when no state file exists for the given brief name."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        result = store.load("nonexistent-skill")

        assert result is None

    def test_exists_returns_true_when_state_exists(self, tmp_path: Path) -> None:
        """exists() returns True when a state file exists."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        state = PipelineState(brief_name="test-skill")
        store.save(state)

        assert store.exists("test-skill") is True

    def test_exists_returns_false_when_no_state(self, tmp_path: Path) -> None:
        """exists() returns False when no state file exists."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")

        assert store.exists("nonexistent") is False

    def test_creates_state_dir_if_not_exists(self, tmp_path: Path) -> None:
        """CheckpointStore creates the state directory if it doesn't exist."""
        from skill_builder.checkpoint import CheckpointStore

        state_dir = tmp_path / "deeply" / "nested" / "state"
        assert not state_dir.exists()

        store = CheckpointStore(state_dir=state_dir)
        state = PipelineState(brief_name="test-skill")
        store.save(state)

        assert state_dir.exists()
        assert (state_dir / "test-skill.json").exists()

    def test_save_updates_updated_at(self, tmp_path: Path) -> None:
        """save() updates the updated_at field before writing."""
        from skill_builder.checkpoint import CheckpointStore

        store = CheckpointStore(state_dir=tmp_path / "state")
        old_time = datetime(2020, 1, 1, tzinfo=UTC)
        state = PipelineState(brief_name="test-skill", updated_at=old_time)
        store.save(state)
        loaded = store.load("test-skill")

        assert loaded is not None
        assert loaded.updated_at > old_time
