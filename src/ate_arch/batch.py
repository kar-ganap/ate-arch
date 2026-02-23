"""Batch scaffolding and run verification utilities."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ate_arch.harness import (
    DATA_DIR,
    load_metadata,
    scaffold_run,
)
from ate_arch.models import Architecture, PartitionCondition


class VerificationIssue(BaseModel):
    """A single issue found during run verification."""

    run_id: str
    category: str
    detail: str


class VerificationReport(BaseModel):
    """Result of verifying a run's readiness or completeness."""

    run_id: str
    passed: bool
    issues: list[VerificationIssue]


# --- Batch scaffolding ---

_ALL_RUN_NUMBERS = [1, 2, 3, 4, 5]


def batch_scaffold(
    architectures: list[Architecture] | None = None,
    partitions: list[PartitionCondition] | None = None,
    run_numbers: list[int] | None = None,
    *,
    data_dir: Path | None = None,
) -> list[Path]:
    """Scaffold multiple runs. None means all values. Returns list of run dirs."""
    archs = architectures or list(Architecture)
    parts = partitions or list(PartitionCondition)
    nums = run_numbers or _ALL_RUN_NUMBERS

    paths: list[Path] = []
    for arch in archs:
        for part in parts:
            for num in nums:
                run_dir = scaffold_run(arch, part, num, data_dir=data_dir)
                paths.append(run_dir)
    return paths


# --- Structural verification (pre-run) ---

_STRUCTURAL_FILES = ["session_guide.md", "metadata.json", "interview_state.json"]


def verify_run_structural(run_id: str, *, data_dir: Path | None = None) -> VerificationReport:
    """Check that a run directory has all required files for execution."""
    base = data_dir or DATA_DIR
    run_dir = base / "runs" / run_id
    issues: list[VerificationIssue] = []

    if not run_dir.exists():
        issues.append(
            VerificationIssue(
                run_id=run_id,
                category="missing_directory",
                detail=f"Run directory does not exist: {run_dir}",
            )
        )
        return VerificationReport(run_id=run_id, passed=False, issues=issues)

    for filename in _STRUCTURAL_FILES:
        path = run_dir / filename
        if not path.exists():
            issues.append(
                VerificationIssue(
                    run_id=run_id,
                    category="missing_file",
                    detail=f"{filename} not found",
                )
            )
        elif path.stat().st_size == 0:
            issues.append(
                VerificationIssue(
                    run_id=run_id,
                    category="empty_file",
                    detail=f"{filename} is empty",
                )
            )

    return VerificationReport(
        run_id=run_id,
        passed=len(issues) == 0,
        issues=issues,
    )


# --- Completeness verification (post-run) ---


def verify_run_complete(run_id: str, *, data_dir: Path | None = None) -> VerificationReport:
    """Check that a run has completed successfully with all artifacts."""
    # First check structural requirements
    structural = verify_run_structural(run_id, data_dir=data_dir)
    issues = list(structural.issues)

    if not structural.passed:
        return VerificationReport(run_id=run_id, passed=False, issues=issues)

    base = data_dir or DATA_DIR
    run_dir = base / "runs" / run_id

    # Check architecture.md
    arch_path = run_dir / "architecture.md"
    if not arch_path.exists():
        issues.append(
            VerificationIssue(
                run_id=run_id,
                category="missing_file",
                detail="architecture.md not found",
            )
        )
    elif not arch_path.read_text().strip():
        issues.append(
            VerificationIssue(
                run_id=run_id,
                category="empty_file",
                detail="architecture.md is empty",
            )
        )

    # Check wall_clock_minutes in metadata
    try:
        metadata = load_metadata(run_dir)
        if metadata.wall_clock_minutes <= 0:
            issues.append(
                VerificationIssue(
                    run_id=run_id,
                    category="invalid_metadata",
                    detail="wall_clock_minutes is 0 — metadata not updated after run",
                )
            )
    except Exception:
        issues.append(
            VerificationIssue(
                run_id=run_id,
                category="invalid_metadata",
                detail="Failed to parse metadata.json",
            )
        )

    return VerificationReport(
        run_id=run_id,
        passed=len(issues) == 0,
        issues=issues,
    )
