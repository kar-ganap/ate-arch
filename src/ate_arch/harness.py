"""Execution harness for experimental runs."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ate_arch.config import (
    CONFIG_DIR,
    load_all_stakeholders,
    load_partitions,
    load_scenario,
)
from ate_arch.models import (
    Architecture,
    InterviewTurn,
    Partition,
    PartitionCondition,
    RunMetadata,
)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SCENARIO_ID = "scenario_b"


# --- Run ID ---


def make_run_id(
    architecture: Architecture,
    partition_condition: PartitionCondition,
    run_num: int,
) -> str:
    """Generate a deterministic run ID. E.g., 'control-A-1'."""
    return f"{architecture.value}-{partition_condition.value}-{run_num}"


# --- Directory management ---


def get_run_dir(run_id: str, *, data_dir: Path | None = None) -> Path:
    """Get (and create) the run directory."""
    base = data_dir or DATA_DIR
    run_dir = base / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# --- Scaffolding ---


def scaffold_run(
    architecture: Architecture,
    partition_condition: PartitionCondition,
    run_num: int,
    *,
    data_dir: Path | None = None,
) -> Path:
    """Create run directory with session guide, metadata template, and notes."""
    run_id = make_run_id(architecture, partition_condition, run_num)
    run_dir = get_run_dir(run_id, data_dir=data_dir)

    # Session guide (always overwritten)
    guide = render_session_guide(run_id, architecture, partition_condition)
    (run_dir / "session_guide.md").write_text(guide)

    # Notes placeholder (never overwritten)
    notes_path = run_dir / "notes.md"
    if not notes_path.exists():
        notes_path.write_text(f"# Notes: {run_id}\n\n")

    # Empty interview state
    state_path = run_dir / "interview_state.json"
    if not state_path.exists():
        state_path.write_text("{}")

    # Metadata template
    metadata = RunMetadata(
        run_id=run_id,
        architecture=architecture,
        partition_condition=partition_condition,
    )
    save_metadata(metadata, run_dir)

    return run_dir


# --- Prompt generation ---


def _get_partition(partition_condition: PartitionCondition) -> Partition:
    """Load the partition for a given condition."""
    partitions = load_partitions(SCENARIO_ID)
    for p in partitions:
        if p.condition == partition_condition:
            return p
    msg = f"Partition condition {partition_condition} not found"
    raise ValueError(msg)


def _stakeholder_roster(stakeholder_ids: list[str]) -> str:
    """Build a name+role roster from stakeholder IDs."""
    stakeholders = {s.id: s for s in load_all_stakeholders(SCENARIO_ID)}
    lines = []
    for sid in stakeholder_ids:
        s = stakeholders[sid]
        lines.append(f"- **{s.name}** ({s.role}) — ID: `{s.id}`")
    return "\n".join(lines)


def get_opening_prompt(
    architecture: Architecture,
    partition_condition: PartitionCondition,
    *,
    agent_num: int = 0,
    run_num: int = 0,
) -> str:
    """Generate the opening prompt for a run."""
    scenario = load_scenario(SCENARIO_ID)
    partition = _get_partition(partition_condition)
    run_id = make_run_id(architecture, partition_condition, run_num)

    if architecture == Architecture.CONTROL:
        return _control_prompt(partition, scenario, run_id)
    return _treatment_prompt(partition, scenario, run_id, agent_num)


def _control_prompt(partition: Partition, scenario: object, run_id: str) -> str:
    """Generate the control (hub-and-spoke) opening prompt."""
    agent_1_roster = _stakeholder_roster(partition.agent_1_stakeholders)
    agent_2_roster = _stakeholder_roster(partition.agent_2_stakeholders)

    return f"""\
You are leading the design of a Multi-Region Data Platform architecture.

## Scenario

DataFlow Corp needs a unified data analytics platform spanning 3 geographic \
regions (US, EU, APAC). The platform must serve regional customers with low \
latency, comply with regional regulations (GDPR), support real-time analytics, \
and maintain a unified data model — all while satisfying competing stakeholder \
requirements across security, compliance, operations, architecture, and product.

## Your Team

You have two sub-teams. Each can only interview their assigned stakeholders.

**Agent 1 stakeholders:**
{agent_1_roster}

**Agent 2 stakeholders:**
{agent_2_roster}

## Your Task

1. Use the Task tool to dispatch sub-agents to interview their assigned stakeholders
2. Sub-agents should run: `ate-arch interview {run_id} <stakeholder_id> "your questions"`
3. Review sub-agent reports and dispatch follow-up interviews as needed
4. Synthesize all findings into a final architecture document

## Important Rules

- You CANNOT interview stakeholders directly. You MUST delegate to sub-agents.
- Each sub-agent can only interview stakeholders in their assignment.
- You may dispatch multiple rounds of follow-up interviews.
- Focus on discovering conflicts between stakeholders and resolving them.

## Output Format

Produce a markdown architecture document with:
- System overview and high-level design
- Component architecture
- Data flow and control flow
- Stakeholder requirements traceability matrix
- Conflict identification and resolution log
- Trade-off analysis with reasoning
- Any hidden dependencies discovered

Save the final document as `architecture.md` in the current directory."""


def _treatment_prompt(
    partition: Partition,
    scenario: object,
    run_id: str,
    agent_num: int = 0,
) -> str:
    """Generate the treatment (symmetric peers) opening prompt."""
    agent_1_roster = _stakeholder_roster(partition.agent_1_stakeholders)
    agent_2_roster = _stakeholder_roster(partition.agent_2_stakeholders)

    return f"""\
You are leading the design of a Multi-Region Data Platform architecture.

## Scenario

DataFlow Corp needs a unified data analytics platform spanning 3 geographic \
regions (US, EU, APAC). The platform must serve regional customers with low \
latency, comply with regional regulations (GDPR), support real-time analytics, \
and maintain a unified data model — all while satisfying competing stakeholder \
requirements across security, compliance, operations, architecture, and product.

## Your Team

You have two peer agents. Each can only interview their assigned stakeholders, \
but they can communicate directly with each other to share findings and \
coordinate.

**Agent 1 stakeholders:**
{agent_1_roster}

**Agent 2 stakeholders:**
{agent_2_roster}

## Your Task

1. Use the Task tool to dispatch two peer agents to interview their assigned \
stakeholders
2. Agents should run: `ate-arch interview {run_id} <stakeholder_id> "your questions"`
3. Agents should share findings with each other and coordinate directly — \
especially on conflicts that span both sets of stakeholders
4. Agents should collaboratively produce the final architecture document

## Important Rules

- You CANNOT interview stakeholders directly. You MUST delegate to peer agents.
- Each agent can only interview stakeholders in their assignment.
- Agents should communicate with each other to share findings and resolve \
cross-team conflicts. They do NOT need to go through you.
- You may dispatch multiple rounds of follow-up interviews.
- Focus on discovering conflicts between stakeholders and resolving them.

## Output Format

Produce a markdown architecture document with:
- System overview and high-level design
- Component architecture
- Data flow and control flow
- Stakeholder requirements traceability matrix
- Conflict identification and resolution log
- Trade-off analysis with reasoning
- Any hidden dependencies discovered

Save the final document as `architecture.md` in the current directory."""


# --- Session guide ---


def render_session_guide(
    run_id: str,
    architecture: Architecture,
    partition_condition: PartitionCondition,
) -> str:
    """Render a human-readable session guide for a run."""
    partition = _get_partition(partition_condition)
    if architecture == Architecture.CONTROL:
        arch_label = "Hub-and-Spoke (Control)"
    else:
        arch_label = "Symmetric Peers (Treatment)"

    agent_1_roster = _stakeholder_roster(partition.agent_1_stakeholders)
    agent_2_roster = _stakeholder_roster(partition.agent_2_stakeholders)

    # Extract run number from run_id (e.g., "control-A-1" -> 1)
    run_num = int(run_id.rsplit("-", 1)[1])
    prompt = get_opening_prompt(architecture, partition_condition, run_num=run_num)

    env_note = ""
    if architecture == Architecture.CONTROL:
        env_note = "Ensure `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is **unset**."
    else:
        env_note = "Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`."

    return f"""\
# Session Guide: {run_id}

## Run Configuration

- **Run ID**: {run_id}
- **Architecture**: {arch_label}
- **Partition**: {partition_condition.value} \
({len(partition.within_partition_conflicts)} within, \
{len(partition.cross_partition_conflicts)} cross)
- **Time Limit**: 30 minutes (soft cap)

## Environment Setup

1. Record `claude --version`
2. {env_note}
3. Ensure `ANTHROPIC_API_KEY` is set (for stakeholder simulation)

## Partition Assignment

**Agent 1:**
{agent_1_roster}

**Agent 2:**
{agent_2_roster}

## Opening Prompt

Copy-paste the following into the Claude Code session:

```
{prompt}
```

## Data Collection Checklist

- [ ] Record Claude Code version in metadata
- [ ] Record start time
- [ ] Monitor session (Escape if stuck > 5 min)
- [ ] Record end time and wall-clock duration
- [ ] Copy final `architecture.md` to run directory
- [ ] Note interview count (how many `ate-arch interview` calls)
- [ ] Record observations in `notes.md`
- [ ] Run `ate-arch update-metadata {run_id} --wall-clock <minutes> --model <model>`
"""


# --- Preflight check ---


def preflight_check(scenario_id: str = SCENARIO_ID) -> list[str]:
    """Validate environment readiness. Returns list of issues (empty = good)."""
    issues: list[str] = []

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        issues.append("ANTHROPIC_API_KEY environment variable is not set")

    # Check scenario loads
    try:
        scenario = load_scenario(scenario_id)
    except Exception as e:
        issues.append(f"Failed to load scenario '{scenario_id}': {e}")
        return issues  # Can't continue without scenario

    # Check all stakeholders load
    for sid in scenario.stakeholder_ids:
        try:
            from ate_arch.config import load_stakeholder

            load_stakeholder(scenario_id, sid)
        except Exception as e:
            issues.append(f"Failed to load stakeholder '{sid}': {e}")

    # Check partitions load
    try:
        partitions = load_partitions(scenario_id)
        if len(partitions) != 3:
            issues.append(f"Expected 3 partitions, got {len(partitions)}")
    except Exception as e:
        issues.append(f"Failed to load partitions: {e}")

    # Check config dir exists
    if not CONFIG_DIR.exists():
        issues.append(f"Config directory not found: {CONFIG_DIR}")

    return issues


# --- Metadata persistence ---


def save_metadata(metadata: RunMetadata, run_dir: Path) -> Path:
    """Save run metadata to JSON."""
    path = run_dir / "metadata.json"
    path.write_text(metadata.model_dump_json(indent=2))
    return path


def load_metadata(run_dir: Path) -> RunMetadata:
    """Load run metadata from JSON."""
    path = run_dir / "metadata.json"
    return RunMetadata.model_validate_json(path.read_text())


# --- Interview state persistence ---


def save_interview_state(state: dict[str, list[InterviewTurn]], run_dir: Path) -> Path:
    """Save interview state (per-stakeholder turn history) to JSON."""
    path = run_dir / "interview_state.json"
    serialized: dict[str, list[dict[str, object]]] = {}
    for sid, turns in state.items():
        serialized[sid] = [t.model_dump(mode="json") for t in turns]
    path.write_text(json.dumps(serialized, indent=2))
    return path


def load_interview_state(run_dir: Path) -> dict[str, list[InterviewTurn]]:
    """Load interview state from JSON. Returns empty dict if file doesn't exist."""
    path = run_dir / "interview_state.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    result: dict[str, list[InterviewTurn]] = {}
    for sid, turns_data in raw.items():
        result[sid] = [InterviewTurn.model_validate(t) for t in turns_data]
    return result
