# Agent Teams Eval — Architecture Design (ate-arch)

## Overview

Experimental comparison of Claude Code with Agent Teams (symmetric peers) vs
default Claude Code (hub-and-spoke subagents) for SW architecture design with
simulated stakeholder requirements gathering. 2 architectures × 3 partition
conditions × 5 runs = 30 total runs. 4-layer rubric scoring.

Third in the ate series. Predecessors found ceiling effects and zero
communication on bug-fixing (ate) and feature implementation (ate-features).
This experiment structures information asymmetry by construction to force
cross-agent communication.

## Tech Stack

- Python 3.11+ with uv
- Pydantic for data models
- Typer for CLI
- PyYAML for config
- pytest + ruff + mypy (strict)
- hatchling build backend

## Conventions

- TDD: tests before code, validation gates (`make test`, `make lint`, `make typecheck`)
- No Co-Authored-By in commits
- Phase branches off main, user merges manually
- `docs/experiment-design.md` is the north star
- Raw data in `data/` (gitignored contents), config in `config/` (committed)
- Dependency groups: core (always), dev (always), scoring (Phase 4+), analysis (Phase 7+)

## Project Structure

```
ate-arch/
├── CLAUDE.md                  # This file (living state)
├── Makefile                   # test, lint, typecheck shortcuts
├── pyproject.toml             # uv + hatchling + ruff + mypy + pytest
├── config/
│   ├── scenarios/             # Scenario definitions (YAML)
│   ├── stakeholders/          # Per-stakeholder constraint sheets
│   ├── partitions.yaml        # A/B/C conflict partition assignments
│   ├── treatments.yaml        # Control + treatment definitions
│   └── rubric.yaml            # 4-layer rubric weights + criteria
├── docs/
│   ├── desiderata.md          # Immutable principles (9 items)
│   ├── process.md             # Phase lifecycle & validation gates
│   ├── experiment-design.md   # THE NORTH STAR
│   └── phases/                # plan + retro per phase
├── data/                      # Raw experiment data (gitignored contents)
│   ├── runs/                  # Per-run directories (scaffolded)
│   ├── transcripts/
│   ├── outputs/               # Architecture docs produced by agents
│   ├── scores/
│   └── comms/                 # Communication analysis summaries
├── src/ate_arch/
│   ├── models.py              # Pydantic models
│   ├── config.py              # YAML loading
│   ├── cli.py                 # Typer CLI
│   ├── simulator.py           # LLM stakeholder simulator
│   ├── harness.py             # Execution harness
│   ├── scoring.py             # 4-layer rubric scoring
│   ├── batch.py               # Batch scaffolding & verification
│   ├── comms.py               # Communication analysis
│   └── analysis.py            # Statistical analysis
├── tests/
│   └── unit/                  # Mocked tests
└── scripts/                   # Utility scripts
```

## Key References

- `docs/desiderata.md` — Immutable principles (9 items)
- `docs/process.md` — Phase lifecycle (PLAN → TEST → IMPLEMENT → RETRO)
- `docs/experiment-design.md` — Full experiment protocol
- Prior experiments: `../ate/docs/findings.md`, `../ate-features/docs/findings.md`

## Current State

**Phase 6 in progress (tooling complete, execution pending).** 297 unit tests.
4 pilot runs scored + retroactive comms analysis. Phase 6 added: indirect
collaboration tracking (FileOperation/IndirectCollaboration), relay transparency
metric (RelayEvent/RelayAnalysis), comms persistence, `postprocess` CLI command,
enhanced `list-runs` with scored/complete/scaffolded status. Retroactive analysis
on all 4 pilots confirms: zero indirect collaboration detected (transcript
opacity — all file ops appear coordinator-level in Agent Teams), zero relay
events (Task tool returns "Spawned successfully", not agent reports). 16 new
runs pending.

## Phases

| Phase | Branch | Status |
|-------|--------|--------|
| 0 | `phase-0-scaffold` | Complete |
| 1 | `phase-1-scenario` | Complete |
| 2 | `phase-2-simulator` | Complete |
| 3 | `phase-3-harness` | Complete |
| 4 | `phase-4-rubric` | Complete |
| 5 | `phase-5-pilot` | Complete |
| 6 | `phase-6-execution` | In progress (tooling done, runs pending) |
| 7 | `phase-7-analysis` | Pending |

## Known Gotchas

- pyproject.toml: `dependencies` must come before `[project.scripts]` in the
  `[project]` table, otherwise hatchling fails with a confusing error
- Claude Code JSONL transcripts nest tool calls in `message.content[]` arrays,
  not at root level. comms.py `_iter_tool_uses()` handles both formats.
- Agent Teams SendMessage calls are all coordinator → agent in practice. Zero
  peer-to-peer messages observed across 3 ate experiments. Indirect
  collaboration happens through shared file I/O (Read/Edit on same file).
- Treatment prompt must be from lead-agent vantage (sees all stakeholders),
  not from individual peer's perspective.
- Agent Teams transcript opacity: treatment transcripts have zero agentIds in
  progress entries. All file operations appear coordinator-level. Indirect
  collaboration detection requires agentId attribution, which is unavailable.
- Agent Teams Task tool results are just "Spawned successfully" — no
  substantive agent reports. Relay transparency metric requires a different
  matching strategy (e.g., pairing SendMessages by temporal sequence).
