"""Tests for ate_arch.harness — execution harness for experimental runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ate_arch.harness import (
    get_opening_prompt,
    get_run_dir,
    load_interview_state,
    load_metadata,
    make_run_id,
    preflight_check,
    render_session_guide,
    save_interview_state,
    save_metadata,
    scaffold_run,
)
from ate_arch.models import (
    Architecture,
    InterviewTurn,
    PartitionCondition,
    RunMetadata,
)

# --- make_run_id ---


class TestMakeRunId:
    def test_control_a_1(self) -> None:
        assert make_run_id(Architecture.CONTROL, PartitionCondition.A, 1) == "control-A-1"

    def test_treatment_b_3(self) -> None:
        assert make_run_id(Architecture.TREATMENT, PartitionCondition.B, 3) == "treatment-B-3"

    def test_control_c_5(self) -> None:
        assert make_run_id(Architecture.CONTROL, PartitionCondition.C, 5) == "control-C-5"


# --- get_run_dir ---


class TestGetRunDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        run_dir = get_run_dir("control-A-1", data_dir=tmp_path)
        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        run_dir = get_run_dir("treatment-B-2", data_dir=tmp_path)
        assert run_dir == tmp_path / "runs" / "treatment-B-2"

    def test_idempotent(self, tmp_path: Path) -> None:
        dir1 = get_run_dir("control-A-1", data_dir=tmp_path)
        dir2 = get_run_dir("control-A-1", data_dir=tmp_path)
        assert dir1 == dir2


# --- scaffold_run ---


class TestScaffoldRun:
    def test_creates_session_guide(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        assert (run_dir / "session_guide.md").exists()

    def test_creates_metadata(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        assert (run_dir / "metadata.json").exists()

    def test_creates_notes(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        assert (run_dir / "notes.md").exists()

    def test_creates_empty_interview_state(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        assert (run_dir / "interview_state.json").exists()
        state = json.loads((run_dir / "interview_state.json").read_text())
        assert state == {}

    def test_notes_not_overwritten_on_rescaffold(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        (run_dir / "notes.md").write_text("# My observations\nSomething important")
        # Re-scaffold
        scaffold_run(Architecture.CONTROL, PartitionCondition.A, 1, data_dir=tmp_path)
        assert "Something important" in (run_dir / "notes.md").read_text()

    def test_returns_correct_run_dir(self, tmp_path: Path) -> None:
        run_dir = scaffold_run(Architecture.TREATMENT, PartitionCondition.B, 2, data_dir=tmp_path)
        assert run_dir.name == "treatment-B-2"


# --- get_opening_prompt ---


class TestGetOpeningPrompt:
    def test_control_prompt_has_scenario(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        assert "Multi-Region Data Platform" in prompt

    def test_control_prompt_has_delegation_instruction(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        has_delegation = (
            "Task tool" in prompt or "sub-agent" in prompt.lower() or "subagent" in prompt.lower()
        )
        assert has_delegation

    def test_control_prompt_forbids_direct_interview(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        assert "cannot interview" in prompt.lower() or "must delegate" in prompt.lower()

    def test_control_prompt_has_stakeholder_names(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        # Partition A: agent 1 = CSO, Compliance, EU Ops
        assert "Elena Vasquez" in prompt
        assert "Marcus Chen" in prompt

    def test_control_prompt_has_no_constraints(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        # Should NOT contain actual constraint details
        assert "HC-S1-1" not in prompt
        assert "AES-256" not in prompt

    def test_control_prompt_has_interview_command(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        assert "ate-arch interview" in prompt

    def test_control_prompt_has_output_format(self) -> None:
        prompt = get_opening_prompt(Architecture.CONTROL, PartitionCondition.A)
        assert "architecture" in prompt.lower()

    def test_treatment_prompt_has_assigned_stakeholders(self) -> None:
        prompt = get_opening_prompt(Architecture.TREATMENT, PartitionCondition.A, agent_num=1)
        # Agent 1 in partition A: CSO, Compliance, EU Ops
        assert "Elena Vasquez" in prompt

    def test_treatment_prompt_mentions_peer(self) -> None:
        prompt = get_opening_prompt(Architecture.TREATMENT, PartitionCondition.A, agent_num=1)
        assert "peer" in prompt.lower() or "partner" in prompt.lower()

    def test_treatment_prompt_has_interview_command(self) -> None:
        prompt = get_opening_prompt(Architecture.TREATMENT, PartitionCondition.A, agent_num=1)
        assert "ate-arch interview" in prompt


# --- render_session_guide ---


class TestRenderSessionGuide:
    def test_guide_contains_run_id(self) -> None:
        guide = render_session_guide("control-A-1", Architecture.CONTROL, PartitionCondition.A)
        assert "control-A-1" in guide

    def test_guide_contains_architecture(self) -> None:
        guide = render_session_guide("control-A-1", Architecture.CONTROL, PartitionCondition.A)
        assert "control" in guide.lower() or "hub-and-spoke" in guide.lower()

    def test_guide_contains_opening_prompt(self) -> None:
        guide = render_session_guide("control-A-1", Architecture.CONTROL, PartitionCondition.A)
        assert "ate-arch interview" in guide

    def test_guide_contains_checklist(self) -> None:
        guide = render_session_guide("control-A-1", Architecture.CONTROL, PartitionCondition.A)
        assert "checklist" in guide.lower() or "- [" in guide


# --- preflight_check ---


class TestPreflightCheck:
    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        issues = preflight_check()
        assert len(issues) == 0

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        issues = preflight_check()
        assert any("ANTHROPIC_API_KEY" in i for i in issues)


# --- save/load_metadata ---


class TestMetadata:
    def _make_metadata(self) -> RunMetadata:
        return RunMetadata(
            run_id="control-A-1",
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
            claude_code_version="1.0.0",
            model="claude-opus-4-6",
            started_at=datetime(2026, 2, 22, 10, 0, 0, tzinfo=UTC),
            wall_clock_minutes=23.5,
            interview_count=12,
        )

    def test_save_creates_file(self, tmp_path: Path) -> None:
        metadata = self._make_metadata()
        path = save_metadata(metadata, tmp_path)
        assert path.exists()
        assert path.name == "metadata.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        original = self._make_metadata()
        save_metadata(original, tmp_path)
        loaded = load_metadata(tmp_path)
        assert loaded.run_id == original.run_id
        assert loaded.architecture == original.architecture
        assert loaded.wall_clock_minutes == original.wall_clock_minutes
        assert loaded.interview_count == original.interview_count


# --- save/load_interview_state ---


class TestInterviewState:
    def _make_turns(self) -> dict[str, list[InterviewTurn]]:
        return {
            "security_officer": [
                InterviewTurn(
                    question="What are your encryption requirements?",
                    response="AES-256 for all data at rest.",
                    turn_number=1,
                    timestamp=datetime(2026, 2, 22, 10, 0, 0, tzinfo=UTC),
                ),
                InterviewTurn(
                    question="What about key management?",
                    response="HSMs preferred for key management.",
                    turn_number=2,
                    timestamp=datetime(2026, 2, 22, 10, 1, 0, tzinfo=UTC),
                ),
            ],
        }

    def test_save_creates_file(self, tmp_path: Path) -> None:
        state = self._make_turns()
        path = save_interview_state(state, tmp_path)
        assert path.exists()
        assert path.name == "interview_state.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        original = self._make_turns()
        save_interview_state(original, tmp_path)
        loaded = load_interview_state(tmp_path)
        assert "security_officer" in loaded
        assert len(loaded["security_officer"]) == 2
        assert loaded["security_officer"][0].question == "What are your encryption requirements?"
        assert loaded["security_officer"][1].response == "HSMs preferred for key management."

    def test_empty_state(self, tmp_path: Path) -> None:
        save_interview_state({}, tmp_path)
        loaded = load_interview_state(tmp_path)
        assert loaded == {}

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        loaded = load_interview_state(tmp_path)
        assert loaded == {}
