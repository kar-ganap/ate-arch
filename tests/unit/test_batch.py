"""Tests for ate_arch.batch — Batch scaffolding and run verification."""

from __future__ import annotations

from pathlib import Path

from ate_arch.batch import (
    VerificationIssue,
    VerificationReport,
    batch_scaffold,
    verify_run_complete,
    verify_run_structural,
)
from ate_arch.models import Architecture, PartitionCondition, RunMetadata

# --- Model tests ---


class TestVerificationIssue:
    def test_creation(self) -> None:
        issue = VerificationIssue(
            run_id="control-A-1",
            category="missing_file",
            detail="session_guide.md not found",
        )
        assert issue.run_id == "control-A-1"
        assert issue.category == "missing_file"
        assert issue.detail == "session_guide.md not found"


class TestVerificationReport:
    def test_passed_report(self) -> None:
        report = VerificationReport(
            run_id="control-A-1",
            passed=True,
            issues=[],
        )
        assert report.passed
        assert report.issues == []

    def test_failed_report(self) -> None:
        issue = VerificationIssue(
            run_id="control-A-1",
            category="missing_file",
            detail="metadata.json not found",
        )
        report = VerificationReport(
            run_id="control-A-1",
            passed=False,
            issues=[issue],
        )
        assert not report.passed
        assert len(report.issues) == 1


# --- batch_scaffold tests ---


class TestBatchScaffold:
    def test_scaffold_all_30(self, tmp_path: Path) -> None:
        """Scaffold all 30 runs (2 arch x 3 partitions x 5 runs)."""
        paths = batch_scaffold(data_dir=tmp_path)
        assert len(paths) == 30
        # Spot check specific runs
        run_ids = {p.name for p in paths}
        assert "control-A-1" in run_ids
        assert "treatment-C-5" in run_ids

    def test_scaffold_filtered_by_architecture(self, tmp_path: Path) -> None:
        """Scaffold only control runs."""
        paths = batch_scaffold(
            architectures=[Architecture.CONTROL],
            data_dir=tmp_path,
        )
        assert len(paths) == 15  # 1 arch x 3 partitions x 5 runs
        for p in paths:
            assert p.name.startswith("control-")

    def test_scaffold_filtered_by_partition(self, tmp_path: Path) -> None:
        """Scaffold only partition A runs."""
        paths = batch_scaffold(
            partitions=[PartitionCondition.A],
            data_dir=tmp_path,
        )
        assert len(paths) == 10  # 2 arch x 1 partition x 5 runs
        for p in paths:
            assert "-A-" in p.name

    def test_scaffold_filtered_by_run_number(self, tmp_path: Path) -> None:
        """Scaffold only run 1 across all conditions."""
        paths = batch_scaffold(
            run_numbers=[1],
            data_dir=tmp_path,
        )
        assert len(paths) == 6  # 2 arch x 3 partitions x 1 run
        for p in paths:
            assert p.name.endswith("-1")

    def test_scaffold_combined_filter(self, tmp_path: Path) -> None:
        """Scaffold with multiple filters."""
        paths = batch_scaffold(
            architectures=[Architecture.TREATMENT],
            partitions=[PartitionCondition.A, PartitionCondition.B],
            run_numbers=[1, 2],
            data_dir=tmp_path,
        )
        assert len(paths) == 4  # 1 arch x 2 partitions x 2 runs

    def test_scaffold_skips_existing(self, tmp_path: Path) -> None:
        """Re-scaffolding doesn't duplicate — scaffold_run handles idempotency."""
        paths1 = batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        assert len(paths1) == 1
        # Scaffold again — should still return the same path
        paths2 = batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        assert len(paths2) == 1
        assert paths1[0] == paths2[0]

    def test_scaffold_creates_session_guide(self, tmp_path: Path) -> None:
        """Each scaffolded run has session_guide.md."""
        paths = batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        assert (paths[0] / "session_guide.md").exists()

    def test_scaffold_creates_metadata(self, tmp_path: Path) -> None:
        """Each scaffolded run has metadata.json."""
        paths = batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        metadata_path = paths[0] / "metadata.json"
        assert metadata_path.exists()
        metadata = RunMetadata.model_validate_json(metadata_path.read_text())
        assert metadata.run_id == "control-A-1"


# --- verify_run_structural tests ---


class TestVerifyRunStructural:
    def test_valid_run_passes(self, tmp_path: Path) -> None:
        """A fully scaffolded run passes structural verification."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert report.passed
        assert report.issues == []

    def test_missing_session_guide(self, tmp_path: Path) -> None:
        """Missing session_guide.md is flagged."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "metadata.json").write_text("{}")
        (run_dir / "interview_state.json").write_text("{}")

        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("session_guide.md" in i.detail for i in report.issues)

    def test_missing_metadata(self, tmp_path: Path) -> None:
        """Missing metadata.json is flagged."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "session_guide.md").write_text("# Guide")
        (run_dir / "interview_state.json").write_text("{}")

        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("metadata.json" in i.detail for i in report.issues)

    def test_missing_interview_state(self, tmp_path: Path) -> None:
        """Missing interview_state.json is flagged."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "session_guide.md").write_text("# Guide")
        (run_dir / "metadata.json").write_text("{}")

        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("interview_state.json" in i.detail for i in report.issues)

    def test_missing_run_directory(self, tmp_path: Path) -> None:
        """Non-existent run directory is flagged."""
        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("directory" in i.detail.lower() for i in report.issues)

    def test_empty_metadata_file(self, tmp_path: Path) -> None:
        """Empty metadata.json is flagged."""
        run_dir = tmp_path / "runs" / "control-A-1"
        run_dir.mkdir(parents=True)
        (run_dir / "session_guide.md").write_text("# Guide")
        (run_dir / "metadata.json").write_text("")
        (run_dir / "interview_state.json").write_text("{}")

        report = verify_run_structural("control-A-1", data_dir=tmp_path)
        assert not report.passed
        has_issue = any(
            "empty" in i.detail.lower() or "metadata" in i.detail.lower() for i in report.issues
        )
        assert has_issue


# --- verify_run_complete tests ---


class TestVerifyRunComplete:
    def test_complete_run_passes(self, tmp_path: Path) -> None:
        """A run with architecture.md and wall_clock > 0 passes."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        run_dir = tmp_path / "runs" / "control-A-1"
        (run_dir / "architecture.md").write_text("# Architecture\n\nDesign here.")

        # Update metadata with wall_clock_minutes
        metadata = RunMetadata.model_validate_json((run_dir / "metadata.json").read_text())
        updated = metadata.model_copy(update={"wall_clock_minutes": 15.0})
        (run_dir / "metadata.json").write_text(updated.model_dump_json(indent=2))

        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert report.passed
        assert report.issues == []

    def test_missing_architecture_doc(self, tmp_path: Path) -> None:
        """Missing architecture.md is flagged."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("architecture.md" in i.detail for i in report.issues)

    def test_empty_architecture_doc(self, tmp_path: Path) -> None:
        """Empty architecture.md is flagged."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        run_dir = tmp_path / "runs" / "control-A-1"
        (run_dir / "architecture.md").write_text("")

        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("empty" in i.detail.lower() for i in report.issues)

    def test_zero_wall_clock(self, tmp_path: Path) -> None:
        """wall_clock_minutes == 0 is flagged (metadata not updated)."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        run_dir = tmp_path / "runs" / "control-A-1"
        (run_dir / "architecture.md").write_text("# Arch")

        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("wall_clock" in i.detail.lower() for i in report.issues)

    def test_structural_failures_also_flagged(self, tmp_path: Path) -> None:
        """Complete verification also checks structural requirements."""
        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert not report.passed
        # Should flag missing directory
        assert any("directory" in i.detail.lower() for i in report.issues)

    def test_whitespace_only_architecture_doc(self, tmp_path: Path) -> None:
        """Whitespace-only architecture.md is flagged as empty."""
        batch_scaffold(
            architectures=[Architecture.CONTROL],
            partitions=[PartitionCondition.A],
            run_numbers=[1],
            data_dir=tmp_path,
        )
        run_dir = tmp_path / "runs" / "control-A-1"
        (run_dir / "architecture.md").write_text("   \n  \n  ")

        report = verify_run_complete("control-A-1", data_dir=tmp_path)
        assert not report.passed
        assert any("empty" in i.detail.lower() for i in report.issues)
