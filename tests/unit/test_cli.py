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
