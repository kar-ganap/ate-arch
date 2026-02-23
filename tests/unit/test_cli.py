"""Tests for ate_arch.cli — Typer CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ate_arch.cli import app

runner = CliRunner()


class TestScaffoldCommand:
    def test_scaffold_creates_run(self, tmp_path: Path) -> None:
        rv = tmp_path / "runs" / "control-A-1"
        with patch("ate_arch.cli.scaffold_run", return_value=rv) as mock:
            with patch("ate_arch.cli.make_run_id", return_value="control-A-1"):
                result = runner.invoke(
                    app,
                    [
                        "scaffold",
                        "--architecture",
                        "control",
                        "--partition",
                        "A",
                        "--run-number",
                        "1",
                    ],
                )
        assert result.exit_code == 0
        assert "control-A-1" in result.output
        mock.assert_called_once()


class TestPreflightCommand:
    def test_preflight_passes(self, monkeypatch: object) -> None:
        with patch("ate_arch.cli.preflight_check", return_value=[]):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                result = runner.invoke(app, ["preflight"])
        assert result.exit_code == 0
        assert "passed" in result.output.lower()

    def test_preflight_reports_issues(self) -> None:
        with patch("ate_arch.cli.preflight_check", return_value=["Missing API key"]):
            result = runner.invoke(app, ["preflight"])
        assert result.exit_code == 1
        assert "Missing API key" in result.output


class TestInterviewCommand:
    def test_interview_calls_simulator(self, tmp_path: Path) -> None:
        # Mock the run dir to use tmp_path
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "interview_state.json").write_text("{}")

        mock_sim = MagicMock()
        mock_sim.interview.return_value = "I require AES-256 encryption."
        mock_sim.get_transcript.return_value = MagicMock(turns=[])

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.load_interview_state", return_value={}),
            patch("ate_arch.cli.save_interview_state"),
            patch("ate_arch.config.load_stakeholder", return_value=MagicMock()),
            patch("ate_arch.simulator.AnthropicLLMClient"),
            patch("ate_arch.simulator.StakeholderSimulator", return_value=mock_sim),
        ):
            result = runner.invoke(
                app,
                ["interview", "control-A-1", "security_officer", "What are your requirements?"],
            )

        assert result.exit_code == 0
        assert "AES-256" in result.output


class TestUpdateMetadataCommand:
    def test_update_metadata(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)

        mock_metadata = MagicMock()
        mock_metadata.started_at = None

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.load_metadata", return_value=mock_metadata),
            patch("ate_arch.cli.save_metadata"),
        ):
            result = runner.invoke(
                app,
                [
                    "update-metadata",
                    "control-A-1",
                    "--wall-clock",
                    "23.5",
                    "--model",
                    "claude-opus-4-6",
                ],
            )

        assert result.exit_code == 0
        assert "Updated" in result.output


class TestListRunsCommand:
    def test_list_no_runs(self, tmp_path: Path) -> None:
        with patch("ate_arch.cli.DATA_DIR", tmp_path):
            result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "No runs" in result.output

    def test_list_with_runs(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        (runs_dir / "control-A-1").mkdir(parents=True)
        (runs_dir / "treatment-B-2").mkdir(parents=True)
        with patch("ate_arch.cli.DATA_DIR", tmp_path):
            result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "control-A-1" in result.output
        assert "treatment-B-2" in result.output


class TestScoreCommand:
    def test_score_missing_document(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        with patch("ate_arch.cli.get_run_dir", return_value=run_dir):
            result = runner.invoke(app, ["score", "control-A-1"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_score_runs_scoring(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "architecture.md").write_text("# Test architecture")

        mock_scoring = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.l1_constraint_discovery = 0.8
        mock_run_result.l2_conflict_identification = 0.6
        mock_run_result.l3_score.return_value = 0.5
        mock_run_result.l4_hidden_dependencies = 0.25
        mock_run_result.composite_score.return_value = 0.55
        mock_scoring.to_run_result.return_value = mock_run_result

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.DATA_DIR", tmp_path),
            patch("ate_arch.scoring.score_run", return_value=mock_scoring),
            patch("ate_arch.config.load_all_hard_constraints", return_value=[]),
            patch("ate_arch.config.load_conflicts", return_value=[]),
            patch("ate_arch.config.load_all_hidden_dependencies", return_value=[]),
            patch("ate_arch.simulator.AnthropicLLMClient"),
            patch("ate_arch.scoring.save_result"),
            patch("ate_arch.scoring.save_scoring_detail"),
        ):
            result = runner.invoke(app, ["score", "control-A-1"])

        assert result.exit_code == 0
        assert "Scored" in result.output


class TestBatchScaffoldCommand:
    def test_batch_scaffold_all(self, tmp_path: Path) -> None:
        mock_paths = [tmp_path / f"run-{i}" for i in range(30)]
        with patch("ate_arch.batch.batch_scaffold", return_value=mock_paths):
            result = runner.invoke(app, ["batch-scaffold"])
        assert result.exit_code == 0
        assert "30" in result.output

    def test_batch_scaffold_filtered(self, tmp_path: Path) -> None:
        mock_paths = [tmp_path / "run-1"]
        with patch("ate_arch.batch.batch_scaffold", return_value=mock_paths):
            result = runner.invoke(
                app,
                ["batch-scaffold", "--architecture", "control", "--partition", "A"],
            )
        assert result.exit_code == 0
        assert "1" in result.output


class TestVerifyRunCommand:
    def test_verify_structural_pass(self) -> None:
        from ate_arch.batch import VerificationReport

        report = VerificationReport(run_id="control-A-1", passed=True, issues=[])
        with patch("ate_arch.batch.verify_run_structural", return_value=report):
            result = runner.invoke(app, ["verify-run", "control-A-1", "--mode", "structural"])
        assert result.exit_code == 0
        assert "passed" in result.output.lower()

    def test_verify_complete_fail(self) -> None:
        from ate_arch.batch import VerificationIssue, VerificationReport

        report = VerificationReport(
            run_id="control-A-1",
            passed=False,
            issues=[
                VerificationIssue(
                    run_id="control-A-1",
                    category="missing_file",
                    detail="architecture.md not found",
                )
            ],
        )
        with patch("ate_arch.batch.verify_run_complete", return_value=report):
            result = runner.invoke(app, ["verify-run", "control-A-1", "--mode", "complete"])
        assert result.exit_code == 1
        assert "architecture.md" in result.output


class TestAnalyzeCommsCommand:
    def test_analyze_with_messages(self, tmp_path: Path) -> None:
        from ate_arch.comms import CommunicationSummary, PeerMessage

        summary = CommunicationSummary(
            run_id="treatment-A-1",
            total_messages=2,
            peer_messages=[
                PeerMessage(sender="a1", recipient="a2", content_preview="hello"),
                PeerMessage(sender="a2", recipient="a1", content_preview="hi"),
            ],
            unique_pairs=2,
        )
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")
        with patch("ate_arch.comms.analyze_session", return_value=summary):
            result = runner.invoke(app, ["analyze-comms", "treatment-A-1", str(transcript)])
        assert result.exit_code == 0
        assert "2" in result.output  # total messages

    def test_analyze_no_messages(self, tmp_path: Path) -> None:
        from ate_arch.comms import CommunicationSummary

        summary = CommunicationSummary(
            run_id="control-A-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
        )
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")
        with patch("ate_arch.comms.analyze_session", return_value=summary):
            result = runner.invoke(app, ["analyze-comms", "control-A-1", str(transcript)])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_analyze_shows_indirect_collab(self, tmp_path: Path) -> None:
        """analyze-comms shows indirect collaboration info."""
        from ate_arch.comms import (
            CommunicationSummary,
            FileOperation,
            IndirectCollaboration,
        )

        summary = CommunicationSummary(
            run_id="treatment-C-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
            has_indirect_collaboration=True,
            file_collaborations=[
                IndirectCollaboration(
                    file_path="/work/architecture.md",
                    operations=[
                        FileOperation(
                            agent_id="coordinator",
                            operation="Write",
                            file_path="/work/architecture.md",
                        ),
                        FileOperation(
                            agent_id="abc123",
                            operation="Read",
                            file_path="/work/architecture.md",
                        ),
                    ],
                    agent_count=2,
                    is_collaborative=True,
                ),
            ],
        )
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")
        with (
            patch("ate_arch.comms.analyze_session", return_value=summary),
            patch("ate_arch.cli.DATA_DIR", tmp_path),
        ):
            result = runner.invoke(
                app,
                ["analyze-comms", "treatment-C-1", str(transcript)],
            )
        assert result.exit_code == 0
        assert "indirect collaboration" in result.output.lower()

    def test_analyze_shows_relay(self, tmp_path: Path) -> None:
        """analyze-comms shows relay transparency info."""
        from ate_arch.comms import (
            CommunicationSummary,
            PeerMessage,
            RelayAnalysis,
            RelayEvent,
        )

        summary = CommunicationSummary(
            run_id="treatment-A-1",
            total_messages=1,
            peer_messages=[
                PeerMessage(sender="", recipient="agent-2", content_preview="hello"),
            ],
            unique_pairs=1,
            relay_analysis=RelayAnalysis(
                relay_events=[
                    RelayEvent(
                        source_agent="agent-1",
                        target_agent="agent-2",
                        source_content="report",
                        target_content="relay",
                        similarity=0.75,
                    ),
                ],
                mean_similarity=0.75,
                relay_count=1,
            ),
        )
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")
        with (
            patch("ate_arch.comms.analyze_session", return_value=summary),
            patch("ate_arch.cli.DATA_DIR", tmp_path),
        ):
            result = runner.invoke(
                app,
                ["analyze-comms", "treatment-A-1", str(transcript)],
            )
        assert result.exit_code == 0
        assert "relay" in result.output.lower()
        assert "0.75" in result.output


class TestEnhancedListRuns:
    def test_scored_status(self, tmp_path: Path) -> None:
        """Scored runs show [scored] and composite score."""
        import json

        runs_dir = tmp_path / "runs"
        (runs_dir / "control-A-1").mkdir(parents=True)
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        score_data = {
            "run_id": "control-A-1",
            "architecture": "control",
            "partition_condition": "A",
            "l1_constraint_discovery": 1.0,
            "l2_conflict_identification": 1.0,
            "l3_resolutions": [],
            "l4_hidden_dependencies": 0.75,
        }
        (scores_dir / "control-A-1.json").write_text(json.dumps(score_data))

        with patch("ate_arch.cli.DATA_DIR", tmp_path):
            result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "scored" in result.output.lower()

    def test_scaffolded_status(self, tmp_path: Path) -> None:
        """Scaffolded-only runs show [scaffolded]."""
        runs_dir = tmp_path / "runs"
        (runs_dir / "control-A-2").mkdir(parents=True)

        with patch("ate_arch.cli.DATA_DIR", tmp_path):
            result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "scaffolded" in result.output.lower()


class TestPostprocessCommand:
    def test_happy_path(self, tmp_path: Path) -> None:
        """postprocess chains metadata update + verify + score + comms."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "architecture.md").write_text("# Test")
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")

        mock_metadata = MagicMock()
        mock_metadata.started_at = None

        mock_scoring = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.l1_constraint_discovery = 1.0
        mock_run_result.l2_conflict_identification = 1.0
        mock_run_result.l3_score.return_value = 0.75
        mock_run_result.l4_hidden_dependencies = 0.75
        mock_run_result.composite_score.return_value = 0.88
        mock_scoring.to_run_result.return_value = mock_run_result

        from ate_arch.comms import CommunicationSummary

        comms_summary = CommunicationSummary(
            run_id="control-A-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
        )

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.load_metadata", return_value=mock_metadata),
            patch("ate_arch.cli.save_metadata"),
            patch("ate_arch.cli.DATA_DIR", tmp_path),
            patch("ate_arch.scoring.score_run", return_value=mock_scoring),
            patch("ate_arch.config.load_all_hard_constraints", return_value=[]),
            patch("ate_arch.config.load_conflicts", return_value=[]),
            patch("ate_arch.config.load_all_hidden_dependencies", return_value=[]),
            patch("ate_arch.simulator.AnthropicLLMClient"),
            patch("ate_arch.scoring.save_result"),
            patch("ate_arch.scoring.save_scoring_detail"),
            patch("ate_arch.comms.analyze_session", return_value=comms_summary),
        ):
            result = runner.invoke(
                app,
                [
                    "postprocess",
                    "control-A-1",
                    "--wall-clock",
                    "12.3",
                    "--interview-count",
                    "16",
                    "--transcript",
                    str(transcript),
                ],
            )

        assert result.exit_code == 0
        assert "composite" in result.output.lower()

    def test_no_transcript_skips_comms(self, tmp_path: Path) -> None:
        """postprocess without transcript skips comms analysis."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "architecture.md").write_text("# Test")

        mock_metadata = MagicMock()
        mock_metadata.started_at = None

        mock_scoring = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.l1_constraint_discovery = 1.0
        mock_run_result.l2_conflict_identification = 1.0
        mock_run_result.l3_score.return_value = 0.75
        mock_run_result.l4_hidden_dependencies = 0.75
        mock_run_result.composite_score.return_value = 0.88
        mock_scoring.to_run_result.return_value = mock_run_result

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.load_metadata", return_value=mock_metadata),
            patch("ate_arch.cli.save_metadata"),
            patch("ate_arch.cli.DATA_DIR", tmp_path),
            patch("ate_arch.scoring.score_run", return_value=mock_scoring),
            patch("ate_arch.config.load_all_hard_constraints", return_value=[]),
            patch("ate_arch.config.load_conflicts", return_value=[]),
            patch("ate_arch.config.load_all_hidden_dependencies", return_value=[]),
            patch("ate_arch.simulator.AnthropicLLMClient"),
            patch("ate_arch.scoring.save_result"),
            patch("ate_arch.scoring.save_scoring_detail"),
        ):
            result = runner.invoke(
                app,
                [
                    "postprocess",
                    "control-A-1",
                    "--wall-clock",
                    "12.3",
                    "--interview-count",
                    "16",
                ],
            )

        assert result.exit_code == 0
        assert "composite" in result.output.lower()

    def test_missing_architecture_fails(self, tmp_path: Path) -> None:
        """postprocess fails if architecture.md is missing."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)

        mock_metadata = MagicMock()
        mock_metadata.started_at = None

        with (
            patch("ate_arch.cli.get_run_dir", return_value=run_dir),
            patch("ate_arch.cli.load_metadata", return_value=mock_metadata),
            patch("ate_arch.cli.save_metadata"),
        ):
            result = runner.invoke(
                app,
                [
                    "postprocess",
                    "control-A-1",
                    "--wall-clock",
                    "10",
                    "--interview-count",
                    "6",
                ],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
