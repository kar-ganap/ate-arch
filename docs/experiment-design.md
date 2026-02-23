# Experiment Design

The north star for the Agent Teams Eval (Architecture Design) experiment.
All experimental choices live here. Changes require a Change Log entry (see bottom).

## 1. Research Question

In problems where we structurally expect agent teams to outperform subagents,
how much do they actually outperform — and does the magnitude scale with the
degree of cross-agent information dependency?

### Hypotheses Under Test

- **Information asymmetry**: When agents can only access disjoint subsets of
  stakeholders, does peer-to-peer communication (agent teams) produce better
  architectures than hub-and-spoke delegation (subagents)?
- **Scaling with dependency**: Does the team advantage grow as more conflicts
  span across agent partitions (conditions A → B → C)?
- **Communication utility**: In treatment runs, does actual peer communication
  correlate with higher rubric scores?

### Prior Work

Two predecessor experiments:
- **ate** (Ruff bug-fixing): Ceiling effect — 8/8 solve rate, zero communication.
  Bug-fixing in single codebases is structurally biased toward solo agents.
- **ate-features** (LangGraph features): Same ceiling, same zero communication.
  Even with shared subsystems, isolated patch-and-reset protocol eliminated
  collaboration signal.

Both failed because: (a) tasks were too easy for the model, (b) full
observability meant no information discovery was needed, (c) each agent could
solve its part independently.

This experiment addresses all three: (a) architecture design has broad solution
spaces, (b) information is distributed by construction (each agent interviews
only its assigned stakeholders), (c) cross-partition conflicts require
cross-agent information to resolve well.

## 2. Domain

SW architecture design with simulated stakeholder requirements gathering.

Each "run" produces a structured architecture document for a system with
competing stakeholder requirements. Stakeholders are simulated by an LLM
(low temperature) with private constraint sheets that include hard constraints,
preferences, and hidden dependencies.

### Stakeholder Simulation

- Each stakeholder backed by an LLM with a system prompt containing their
  private constraint sheet
- Low temperature (0.1-0.2) for factual adherence to constraint sheet
- Stakeholders do NOT volunteer information unprompted
- Stakeholders do NOT leak other stakeholders' constraints
- Hidden dependencies only revealed when asked specifically enough
- Model and temperature pinned across all runs

## 3. Scenarios

### Scenario B (Primary): Multi-Region Data Platform

A company needs a data platform spanning 3 geographic regions (US, EU, APAC).

**6 stakeholders** (3 per agent partition):
- Security Officer
- Compliance Lead
- Regional Ops (EU)
- Regional Ops (APAC)
- Platform Architect
- Product Manager

~8 hard constraints, ~6 conflicts, ~4 hidden dependencies.
Full definitions in `config/stakeholders/scenario_b/` (Phase 1).

### Scenario C (Backup): Event-Driven Marketplace

If Scenario B doesn't show enough signal. Different conflict structure, same
experimental framework. Details TBD in Phase 1 if needed.

## 4. Architectures

### Control: Hub-and-Spoke Subagents

- `claude` (no env var — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` must be **unset**)
- Lead agent dispatches subagents via `dispatch_interview(agent_id, stakeholder_ids, questions)`
- Subagents interview their assigned stakeholders, return reports to lead
- Lead synthesizes reports into final architecture document
- Lead can dispatch follow-ups (iterative, not one-and-done)
- Lead CANNOT interview stakeholders directly (forces delegation)
- Lead naturally uses Task tool (subagents) — this is Claude's default behavior

### Treatment: Symmetric Peers

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude`
- Each peer agent has `interview(stakeholder_id, questions)` for assigned stakeholders
- Each peer agent has `message_peer(recipient, content)` for cross-agent communication
- Peers collaboratively produce the architecture document
- No lead/subordinate hierarchy

## 5. Partition Conditions

Stakeholders are partitioned between two agents. The conflict graph forms two
natural clusters (Governance: {CSO, Compliance, EU Ops} and Builder: {APAC Ops,
Architect, PM}) connected by 2 bridge conflicts. With 8 conflicts among 6
stakeholders in 3+3 partitions, mathematical constraints limit the achievable
within/cross ratios.

| Condition | Partition | Within | Cross | Ratio | Expected team advantage |
|-----------|-----------|--------|-------|-------|------------------------|
| **A** | {CSO, Comp, EU Ops} \| {APAC, Arch, PM} | 6 | 2 | 75/25 | Minimal |
| **B** | {CSO, Comp, APAC} \| {EU Ops, Arch, PM} | 4 | 4 | 50/50 | Moderate |
| **C** | {CSO, Comp, Arch} \| {EU Ops, APAC, PM} | 2 | 6 | 25/75 | Maximum |

The gradient (75% → 50% → 25% within-partition) provides a monotonic decrease
in within-partition conflicts. The absolute increase from A to C is 4 additional
cross-partition conflicts (from 2 to 6), a 3x increase in cross-boundary
information dependency.

Condition A serves as an internal control: with most conflicts within-partition,
team communication has limited value. If teams show advantage in A, it suggests
the advantage comes from the architecture itself, not from information sharing.

## 6. Experimental Matrix

| Cell | Architecture | Partition | Runs |
|------|-------------|-----------|------|
| Control-A | Hub-and-spoke | A | 5 |
| Control-B | Hub-and-spoke | B | 5 |
| Control-C | Hub-and-spoke | C | 5 |
| Treatment-A | Symmetric peers | A | 5 |
| Treatment-B | Symmetric peers | B | 5 |
| Treatment-C | Symmetric peers | C | 5 |
| **Total** | | | **30** |

## 7. Rubric (4 Layers)

| Layer | What | How | Weight |
|-------|------|-----|--------|
| L1: Constraint Discovery | Did the agent discover each stakeholder's hard constraints? | Checklist: each constraint found/not found (automated) | 0.25 |
| L2: Conflict Identification | Did the agent identify conflicts between stakeholders? | Checklist: each known conflict identified/missed (semi-automated) | 0.25 |
| L3: Conflict Resolution | Quality of resolution for each identified conflict | Categorical: optimal / acceptable / poor / missing (LLM-as-judge) | 0.30 |
| L4: Hidden Dependencies | Did the agent discover non-obvious cross-stakeholder dependencies? | Checklist: each hidden dependency found/not found (semi-automated) | 0.20 |

### L3 Scoring Categories

- **Optimal**: Resolution satisfies both stakeholders' hard constraints with
  minimal compromise on preferences
- **Acceptable**: Resolution satisfies hard constraints but with significant
  preference trade-offs
- **Poor**: Resolution violates one or more hard constraints
- **Missing**: Conflict not addressed in architecture document

### Ground Truth

A reference "optimal" architecture document defines the best-case resolution for
each conflict and dependency. Created in Phase 1 alongside scenario design.

## 8. Output Format

Agents produce a structured architecture document containing:
- System overview and high-level design
- Component architecture (mermaid diagrams)
- Data flow and control flow diagrams
- Stakeholder requirements traceability matrix
- Conflict identification and resolution log
- Trade-off analysis with reasoning
- Hidden dependency analysis (if discovered)

## 9. Execution Protocol

### Shared Protocol (all runs)

- Interactive Claude Code session
- Pin Claude Code version: record `claude --version` before starting
- Pin model: same model for all runs
- Time limit: 30 minutes per run (soft cap)
- Human monitors in real-time, Escape if stuck

### Control Runs

- `claude` (ensure `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is unset)
- Lead agent receives: scenario description, stakeholder list (names + roles
  only, not constraints), partition assignment, output format spec
- Lead uses Task tool to spawn subagents for interviewing

### Treatment Runs

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude`
- Each peer receives: scenario description, their assigned stakeholders,
  output format spec, knowledge that a peer exists with the other stakeholders
- Peers coordinate via `message_peer()`

### Each Run is Self-Contained

- Start session → agents interview stakeholders → produce architecture doc → done
- No cumulative state between runs
- ~20-30 min per run
- 30 total runs, can be done in batches

## 10. Measurement

### Primary Analysis

- 2-way ANOVA: Architecture (control vs treatment) × Partition (A, B, C)
- Effect sizes: Cohen's d for treatment vs control at each partition level
- Interaction effect: does team advantage scale with partition level?

### Communication Analysis (treatment runs only)

- Message count between peers
- Content taxonomy: status update / finding shared / question / conflict alert
- Impact: correlation between communication volume/quality and rubric scores

### Secondary Metrics

- Wall-clock time per run
- Token count per run
- Interview count (how many stakeholder interactions)
- Dead ends (approaches attempted then abandoned)

## 11. Cost Model

- All runs under Claude Max subscription
- Total out of pocket: **$0** (no API costs except stakeholder simulation)
- Stakeholder simulation: LLM API costs TBD (estimate: minimal, ~$1-2 total)

## 12. Change Log

| Date | Change | Rationale |
|------|--------|-----------|
| 2026-02-22 | Initial design | Phase 0 scaffolding. Successor to ate and ate-features. |
| 2026-02-22 | Phase 1: Scenario B design, partition math correction | 6 stakeholders, 8 conflicts, 4 hidden dependencies, 3 partition configs. Partition ratios corrected from idealized 100/0, 50/50, 0/100 to achievable 75/25, 50/50, 25/75 based on conflict graph analysis. |
