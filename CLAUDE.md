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
│   └── scores/
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

**Phase 5 in progress.** Tooling complete: `batch.py` (batch scaffolding +
verification), `comms.py` (JSONL transcript parsing + communication analysis),
3 new CLI commands (`batch-scaffold`, `verify-run`, `analyze-comms`), execution
guide. 251 unit tests (all mocked, zero real LLM calls). Live pilot runs
(control-A-1, treatment-A-1, control-C-1) pending.

## Phases

| Phase | Branch | Status |
|-------|--------|--------|
| 0 | `phase-0-scaffold` | Complete |
| 1 | `phase-1-scenario` | Complete |
| 2 | `phase-2-simulator` | Complete |
| 3 | `phase-3-harness` | Complete |
| 4 | `phase-4-rubric` | Complete |
| 5 | `phase-5-pilot` | In Progress |
| 6 | `phase-6-execution` | Pending |
| 7 | `phase-7-analysis` | Pending |

## Known Gotchas

- pyproject.toml: `dependencies` must come before `[project.scripts]` in the
  `[project]` table, otherwise hatchling fails with a confusing error
