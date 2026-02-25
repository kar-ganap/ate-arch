"""CLI entry point for ate-arch."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from ate_arch.harness import (
    DATA_DIR,
    SCENARIO_ID,
    get_run_dir,
    load_interview_state,
    load_metadata,
    make_run_id,
    preflight_check,
    save_interview_state,
    save_metadata,
    scaffold_run,
)
from ate_arch.models import Architecture, PartitionCondition

app = typer.Typer(name="ate-arch", help="Agent Teams Eval: Architecture Design")


@app.callback()
def main() -> None:
    """Agent Teams Eval — Architecture Design experiment tooling."""
    from pathlib import Path

    from dotenv import load_dotenv

    # Load .env from project root (overrides shell env)
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path, override=True)


@app.command()
def scaffold(
    architecture: Architecture = typer.Option(..., help="control or treatment"),
    partition: PartitionCondition = typer.Option(..., help="A, B, or C"),
    run_number: int = typer.Option(..., help="Run number (1-5)"),
) -> None:
    """Scaffold a new experimental run."""
    run_dir = scaffold_run(architecture, partition, run_number)
    run_id = make_run_id(architecture, partition, run_number)
    typer.echo(f"Scaffolded run '{run_id}' at {run_dir}")


@app.command()
def interview(
    run_id: str = typer.Argument(help="Run ID (e.g., control-A-1)"),
    stakeholder_id: str = typer.Argument(help="Stakeholder to interview"),
    questions: str = typer.Argument(help="Questions to ask"),
) -> None:
    """Interview a stakeholder (called by agent during a run)."""
    from ate_arch.config import load_stakeholder
    from ate_arch.simulator import AnthropicLLMClient, StakeholderSimulator

    run_dir = get_run_dir(run_id)

    # Load existing conversation state
    state = load_interview_state(run_dir)
    prior_turns = state.get(stakeholder_id, [])

    # Create simulator with history
    stakeholder = load_stakeholder(SCENARIO_ID, stakeholder_id)
    llm_client = AnthropicLLMClient()
    sim = StakeholderSimulator(
        stakeholder=stakeholder,
        scenario_id=SCENARIO_ID,
        llm_client=llm_client,
        initial_turns=prior_turns if prior_turns else None,
    )

    # Interview
    response = sim.interview(questions)

    # Save updated state
    state[stakeholder_id] = list(sim.get_transcript().turns)
    save_interview_state(state, run_dir)

    # Output response to stdout (agent reads this)
    typer.echo(response)


@app.command(name="preflight")
def preflight_cmd(
    architecture: Architecture | None = typer.Option(None, help="Check env var for architecture"),
) -> None:
    """Run preflight checks before an experimental run."""
    import os

    issues = preflight_check()

    # Check architecture-specific env var
    if architecture is not None:
        agent_teams = os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
        if architecture == Architecture.CONTROL and agent_teams is not None:
            issues.append(
                "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is set but should be unset for control runs"
            )
        elif architecture == Architecture.TREATMENT and agent_teams != "1":
            issues.append("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS should be '1' for treatment runs")

    if issues:
        typer.echo("Preflight issues found:")
        for issue in issues:
            typer.echo(f"  - {issue}")
        raise typer.Exit(1)
    else:
        typer.echo("All preflight checks passed.")


@app.command(name="update-metadata")
def update_metadata_cmd(
    run_id: str = typer.Argument(help="Run ID"),
    wall_clock: float = typer.Option(..., help="Wall-clock minutes"),
    model: str = typer.Option("claude-opus-4-6", help="Model used"),
    claude_version: str = typer.Option("", help="Claude Code version"),
    interview_count: int | None = typer.Option(None, help="Number of interviews"),
    notes: str | None = typer.Option(None, help="Run notes"),
) -> None:
    """Update metadata after a run completes."""
    run_dir = get_run_dir(run_id)
    metadata = load_metadata(run_dir)
    metadata.wall_clock_minutes = wall_clock
    metadata.model = model
    metadata.started_at = metadata.started_at or datetime.now(UTC)
    if claude_version:
        metadata.claude_code_version = claude_version
    if interview_count is not None:
        metadata.interview_count = interview_count
    if notes is not None:
        metadata.notes = notes
    save_metadata(metadata, run_dir)
    typer.echo(f"Updated metadata for '{run_id}'")


@app.command(name="score")
def score_cmd(
    run_id: str = typer.Argument(help="Run ID to score"),
    document_path: str | None = typer.Option(
        None, help="Path to architecture.md (default: run dir)"
    ),
    model: str = typer.Option("claude-haiku-4-5-20251001", help="Model for scoring"),
) -> None:
    """Score an architecture document against the rubric."""
    from pathlib import Path

    from ate_arch.config import (
        load_all_hard_constraints,
        load_all_hidden_dependencies,
        load_conflicts,
    )
    from ate_arch.scoring import (
        save_result,
        save_scoring_detail,
        score_run,
    )
    from ate_arch.simulator import AnthropicLLMClient

    run_dir = get_run_dir(run_id)

    # Load architecture document
    if document_path:
        doc_path = Path(document_path)
    else:
        doc_path = run_dir / "architecture.md"

    if not doc_path.exists():
        typer.echo(f"Architecture document not found: {doc_path}")
        raise typer.Exit(1)

    document = doc_path.read_text()

    # Parse run ID to get architecture and partition
    parts = run_id.split("-")
    arch = Architecture(parts[0])
    partition = PartitionCondition(parts[1])

    # Load scoring config
    constraints = load_all_hard_constraints(SCENARIO_ID)
    conflicts = load_conflicts(SCENARIO_ID)
    dependencies = load_all_hidden_dependencies(SCENARIO_ID)

    # Score
    llm_client = AnthropicLLMClient()
    scoring = score_run(
        run_id,
        document,
        constraints,
        conflicts,
        dependencies,
        llm_client,
        architecture=arch,
        partition_condition=partition,
        model=model,
    )

    # Persist
    scores_dir = DATA_DIR / "scores"
    run_result = scoring.to_run_result(arch, partition)
    save_result(run_result, scores_dir, scoring_model=model)
    save_scoring_detail(scoring, scores_dir, scoring_model=model)

    # Print summary
    from ate_arch.scoring import model_slug

    slug = model_slug(model)
    typer.echo(f"Scored run '{run_id}' ({slug}):")
    typer.echo(f"  L1 (Constraint Discovery): {run_result.l1_constraint_discovery:.2f}")
    typer.echo(f"  L2 (Conflict Identification): {run_result.l2_conflict_identification:.2f}")
    typer.echo(f"  L3 (Resolution Quality): {run_result.l3_score():.2f}")
    typer.echo(f"  L4 (Hidden Dependencies): {run_result.l4_hidden_dependencies:.2f}")
    from ate_arch.models import RubricWeights

    typer.echo(f"  Composite: {run_result.composite_score(RubricWeights()):.2f}")


@app.command(name="list-runs")
def list_runs_cmd() -> None:
    """List all scaffolded runs with status."""
    import re

    runs_dir = DATA_DIR / "runs"
    if not runs_dir.exists():
        typer.echo("No runs directory found.")
        return
    run_dirs = sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
    if not run_dirs:
        typer.echo("No runs found.")
        return

    scores_dir = DATA_DIR / "scores"

    typer.echo(f"Found {len(run_dirs)} run(s):")
    for name in run_dirs:
        run_dir = runs_dir / name
        has_arch = (run_dir / "architecture.md").exists()

        # Find all score files for this run (e.g., control-A-1_haiku.json)
        model_scores: dict[str, float] = {}
        if scores_dir.exists():
            from ate_arch.models import RubricWeights, RunResult

            # Match {name}.json or {name}_{slug}.json, exclude _detail
            pattern = re.compile(re.escape(name) + r"(?:_([a-z]+))?\.json$")
            for score_file in sorted(scores_dir.iterdir()):
                if not score_file.is_file():
                    continue
                m = pattern.match(score_file.name)
                if not m or "_detail" in score_file.name:
                    continue
                slug = m.group(1) or "default"
                try:
                    rr = RunResult.model_validate_json(score_file.read_text())
                    model_scores[slug] = rr.composite_score(RubricWeights())
                except Exception:
                    model_scores[slug] = -1.0

        if model_scores:
            scores_str = "  ".join(
                f"{k}={v:.2f}" if v >= 0 else k
                for k, v in sorted(model_scores.items())
            )
            typer.echo(f"  {name:<20} [scored]  {scores_str}")
        elif has_arch:
            typer.echo(f"  {name:<20} [complete]")
        else:
            typer.echo(f"  {name:<20} [scaffolded]")


@app.command(name="batch-scaffold")
def batch_scaffold_cmd(
    architecture: Architecture | None = typer.Option(None, help="Filter by architecture"),
    partition: PartitionCondition | None = typer.Option(None, help="Filter by partition"),
) -> None:
    """Scaffold multiple runs at once."""
    from ate_arch.batch import batch_scaffold

    archs = [architecture] if architecture else None
    parts = [partition] if partition else None
    paths = batch_scaffold(architectures=archs, partitions=parts)
    typer.echo(f"Scaffolded {len(paths)} run(s).")
    for p in paths:
        typer.echo(f"  {p.name}")


@app.command(name="verify-run")
def verify_run_cmd(
    run_id: str = typer.Argument(help="Run ID to verify"),
    mode: str = typer.Option("structural", help="structural or complete"),
) -> None:
    """Verify a run's readiness or completeness."""
    from ate_arch.batch import verify_run_complete, verify_run_structural

    if mode == "complete":
        report = verify_run_complete(run_id)
    else:
        report = verify_run_structural(run_id)

    if report.passed:
        typer.echo(f"Verification passed for '{run_id}'.")
    else:
        typer.echo(f"Verification failed for '{run_id}':")
        for issue in report.issues:
            typer.echo(f"  [{issue.category}] {issue.detail}")
        raise typer.Exit(1)


@app.command(name="analyze-comms")
def analyze_comms_cmd(
    run_id: str = typer.Argument(help="Run ID"),
    transcript_path: str = typer.Argument(help="Path to JSONL transcript"),
) -> None:
    """Analyze inter-agent communication from a transcript."""
    from pathlib import Path

    from ate_arch.comms import analyze_session, save_comms_summary

    path = Path(transcript_path)
    if not path.exists():
        typer.echo(f"Transcript not found: {path}")
        raise typer.Exit(1)

    summary = analyze_session(run_id, path)

    # Persist
    comms_dir = DATA_DIR / "comms"
    save_comms_summary(summary, comms_dir)

    typer.echo(f"Communication analysis for '{run_id}':")
    typer.echo(f"  Total peer messages: {summary.total_messages}")
    typer.echo(f"  Unique sender→recipient pairs: {summary.unique_pairs}")
    if summary.peer_messages:
        typer.echo("  Messages:")
        for msg in summary.peer_messages:
            typer.echo(f"    {msg.sender} → {msg.recipient}: {msg.content_preview[:80]}")

    # Phase 6: indirect collaboration
    if summary.file_collaborations:
        collab_count = sum(1 for c in summary.file_collaborations if c.is_collaborative)
        typer.echo(f"  Indirect collaboration: {summary.has_indirect_collaboration}")
        typer.echo(f"  File operations tracked: {len(summary.file_collaborations)} files")
        typer.echo(f"  Collaborative files: {collab_count}")
        for fc in summary.file_collaborations:
            label = "collaborative" if fc.is_collaborative else "single-agent"
            typer.echo(f"    {fc.file_path} ({fc.agent_count} agents, {label})")

    # Phase 6: relay transparency
    if summary.relay_analysis is not None:
        ra = summary.relay_analysis
        typer.echo(
            f"  Relay transparency: {ra.relay_count} relays, "
            f"mean similarity {ra.mean_similarity:.2f}"
        )
        for event in ra.relay_events:
            typer.echo(
                f"    {event.source_agent} → lead → {event.target_agent}: "
                f"similarity {event.similarity:.2f}"
            )


@app.command(name="postprocess")
def postprocess_cmd(
    run_id: str = typer.Argument(help="Run ID to postprocess"),
    transcript: str = typer.Argument(help="Path to JSONL transcript"),
    wall_clock: float | None = typer.Option(None, help="Override wall-clock minutes"),
    interview_count: int | None = typer.Option(
        None, help="Override interview count"
    ),
    model: str = typer.Option("claude-opus-4-6", help="Model used for run"),
    scoring_model: str = typer.Option(
        "claude-haiku-4-5-20251001", help="Model for scoring"
    ),
) -> None:
    """Run all post-run processing: metadata → score → comms."""
    from pathlib import Path

    from ate_arch.harness import count_interviews, extract_timestamps_from_transcript

    t_path = Path(transcript)
    if not t_path.exists():
        typer.echo(f"Transcript not found: {t_path}")
        raise typer.Exit(1)

    # Step 1: Update metadata (auto-extract from breadcrumbs)
    run_dir = get_run_dir(run_id)
    metadata = load_metadata(run_dir)
    metadata.model = model

    # Auto-extract from transcript timestamps
    started_at, auto_wall_clock = extract_timestamps_from_transcript(t_path)
    metadata.started_at = metadata.started_at or started_at
    metadata.wall_clock_minutes = wall_clock if wall_clock is not None else auto_wall_clock

    # Auto-count from interview_state.json
    metadata.interview_count = (
        interview_count if interview_count is not None else count_interviews(run_dir)
    )

    save_metadata(metadata, run_dir)
    typer.echo(
        f"Updated metadata for '{run_id}' "
        f"(wall_clock={metadata.wall_clock_minutes:.1f}min, "
        f"interviews={metadata.interview_count})"
    )

    # Step 2: Score
    doc_path = run_dir / "architecture.md"
    if not doc_path.exists():
        typer.echo(f"Architecture document not found: {doc_path}")
        raise typer.Exit(1)

    document = doc_path.read_text()
    parts = run_id.split("-")
    arch = Architecture(parts[0])
    partition = PartitionCondition(parts[1])

    from ate_arch.config import (
        load_all_hard_constraints,
        load_all_hidden_dependencies,
        load_conflicts,
    )
    from ate_arch.scoring import save_result, save_scoring_detail, score_run
    from ate_arch.simulator import AnthropicLLMClient

    constraints = load_all_hard_constraints(SCENARIO_ID)
    conflicts = load_conflicts(SCENARIO_ID)
    dependencies = load_all_hidden_dependencies(SCENARIO_ID)

    llm_client = AnthropicLLMClient()
    scoring = score_run(
        run_id,
        document,
        constraints,
        conflicts,
        dependencies,
        llm_client,
        architecture=arch,
        partition_condition=partition,
        model=scoring_model,
    )

    scores_dir = DATA_DIR / "scores"
    run_result = scoring.to_run_result(arch, partition)
    save_result(run_result, scores_dir, scoring_model=scoring_model)
    save_scoring_detail(scoring, scores_dir, scoring_model=scoring_model)

    from ate_arch.models import RubricWeights
    from ate_arch.scoring import model_slug

    slug = model_slug(scoring_model)
    comp = run_result.composite_score(RubricWeights())
    typer.echo(f"Scored '{run_id}' ({slug}):")
    typer.echo(f"  L1: {run_result.l1_constraint_discovery:.2f}")
    typer.echo(f"  L2: {run_result.l2_conflict_identification:.2f}")
    typer.echo(f"  L3: {run_result.l3_score():.2f}")
    typer.echo(f"  L4: {run_result.l4_hidden_dependencies:.2f}")
    typer.echo(f"  Composite: {comp:.2f}")

    # Step 3: Comms analysis
    from ate_arch.comms import analyze_session, save_comms_summary

    summary = analyze_session(run_id, t_path)
    comms_dir = DATA_DIR / "comms"
    save_comms_summary(summary, comms_dir)
    typer.echo(
        f"  Comms: {summary.total_messages} peer messages, "
        f"indirect collab: {summary.has_indirect_collaboration}"
    )


@app.command(name="rescore")
def rescore_cmd(
    scoring_model: str = typer.Option(..., help="Model to score with"),
    run_ids: str | None = typer.Option(
        None, help="Comma-separated run IDs (default: all with architecture.md)"
    ),
) -> None:
    """Re-score completed runs with a different model."""
    from ate_arch.config import (
        load_all_hard_constraints,
        load_all_hidden_dependencies,
        load_conflicts,
    )
    from ate_arch.scoring import (
        model_slug,
        save_result,
        save_scoring_detail,
        score_run,
    )
    from ate_arch.simulator import AnthropicLLMClient

    runs_dir = DATA_DIR / "runs"
    if not runs_dir.exists():
        typer.echo("No runs directory found.")
        raise typer.Exit(1)

    # Determine which runs to score
    if run_ids:
        ids = [r.strip() for r in run_ids.split(",")]
    else:
        ids = sorted(
            d.name
            for d in runs_dir.iterdir()
            if d.is_dir() and (d / "architecture.md").exists()
        )

    if not ids:
        typer.echo("No completed runs found.")
        return

    slug = model_slug(scoring_model)
    constraints = load_all_hard_constraints(SCENARIO_ID)
    conflicts = load_conflicts(SCENARIO_ID)
    dependencies = load_all_hidden_dependencies(SCENARIO_ID)
    llm_client = AnthropicLLMClient()
    scores_dir = DATA_DIR / "scores"

    from ate_arch.models import RubricWeights

    typer.echo(f"Scoring {len(ids)} run(s) with {slug}:")
    for run_id in ids:
        run_dir = runs_dir / run_id
        doc_path = run_dir / "architecture.md"
        if not doc_path.exists():
            typer.echo(f"  {run_id}: no architecture.md, skipping")
            continue

        document = doc_path.read_text()
        parts = run_id.split("-")
        arch = Architecture(parts[0])
        partition = PartitionCondition(parts[1])

        scoring = score_run(
            run_id,
            document,
            constraints,
            conflicts,
            dependencies,
            llm_client,
            architecture=arch,
            partition_condition=partition,
            model=scoring_model,
        )
        rr = scoring.to_run_result(arch, partition)
        save_result(rr, scores_dir, scoring_model=scoring_model)
        save_scoring_detail(scoring, scores_dir, scoring_model=scoring_model)
        comp = rr.composite_score(RubricWeights())
        typer.echo(f"  {run_id}: {comp:.2f}")


if __name__ == "__main__":
    app()
