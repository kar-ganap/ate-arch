# Agent Teams Eval — Architecture Design (ate-arch)

## Overview

Experimental comparison of Claude Code with Agent Teams (symmetric peers) vs
default Claude Code (hub-and-spoke subagents) for SW architecture design with
simulated stakeholder requirements gathering. 2 architectures × 2 partition
conditions × 8 runs = 32 total runs. 4-layer rubric scoring.

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
- matplotlib + scipy (analysis group)

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
├── README.md                  # Project overview + key findings
├── Makefile                   # test, lint, typecheck shortcuts
├── pyproject.toml             # uv + hatchling + ruff + mypy + pytest
├── config/
│   ├── scenarios/             # Scenario definitions (YAML)
│   ├── stakeholders/          # Per-stakeholder constraint sheets
│   ├── partitions.yaml        # A/B/C conflict partition assignments
│   ├── conflicts.yaml         # 8 conflicts between stakeholders
│   └── rubric.yaml            # 4-layer rubric weights + criteria
├── docs/
│   ├── desiderata.md          # Immutable principles (9 items)
│   ├── process.md             # Phase lifecycle & validation gates
│   ├── experiment-design.md   # THE NORTH STAR
│   ├── findings.md            # Comprehensive findings report (927 lines)
│   ├── architecture.md        # System diagrams (mermaid)
│   ├── figures/               # Generated PNG charts
│   └── phases/                # plan + retro per phase
├── data/                      # Raw experiment data (gitignored contents)
│   ├── runs/                  # Per-run directories (32 scaffolded)
│   ├── transcripts/
│   ├── scores/                # Dual-model: {run_id}_{slug}.json
│   └── comms/                 # Communication analysis summaries
├── src/ate_arch/
│   ├── models.py              # Pydantic models
│   ├── config.py              # YAML loading
│   ├── cli.py                 # Typer CLI
│   ├── simulator.py           # LLM stakeholder simulator
│   ├── harness.py             # Execution harness
│   ├── scoring.py             # 4-layer rubric scoring
│   ├── batch.py               # Batch scaffolding & verification
│   └── comms.py               # Communication analysis
├── tests/
│   └── unit/                  # Mocked tests (330)
└── scripts/
    ├── figures.py             # Matplotlib chart generation
    ├── extract_all.py         # Dual-model score extraction
    └── stats.py               # Statistical analysis (scipy)
```

## Key References

- `docs/desiderata.md` — Immutable principles (9 items)
- `docs/process.md` — Phase lifecycle (PLAN → TEST → IMPLEMENT → RETRO)
- `docs/experiment-design.md` — Full experiment protocol
- `docs/findings.md` — Complete findings with figures
- `docs/architecture.md` — System diagrams
- Series index: https://github.com/kar-ganap/ate-series
- Prior experiments: `../ate/docs/findings.md`, `../ate-features/docs/findings.md`

## Current State

**Phase 7 complete (experiment finished).** 330 unit tests. 32 runs executed
(n=8 per cell), scored by Sonnet 4.6. Statistical analysis complete:
architecture main effect significant (p=0.014, d=+0.99 composite; p=0.011,
d=+1.04 L3). Dose-response gradient confirmed. Blind architectural review
(6 dimensions, 32 docs) independently validates treatment advantage. 927-line
findings report with 4 matplotlib figures and mermaid diagrams. Cross-linked
with ate-series index repo.

## Key Results

| Cell | n | Composite | L3 | L4 |
|------|---|-----------|----|----|
| Control-A | 8 | 0.58 | 0.37 | 0.56 |
| Control-C | 8 | 0.68 | 0.44 | 0.72 |
| Treatment-A | 8 | 0.73 | 0.48 | 0.78 |
| Treatment-C | 8 | 0.88 | 0.80 | 0.88 |

## Phases

| Phase | Branch | Status |
|-------|--------|--------|
| 0 | `phase-0-scaffold` | Complete |
| 1 | `phase-1-scenario` | Complete |
| 2 | `phase-2-simulator` | Complete |
| 3 | `phase-3-harness` | Complete |
| 4 | `phase-4-rubric` | Complete |
| 5 | `phase-5-pilot` | Complete |
| 6 | `phase-6-execution` | Complete |
| 7 | `phase-7-documentation` | Complete |

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
- Score file naming: `{run_id}_{slug}.json` (e.g., `control-A-1_sonnet.json`).
  Backward compatible with legacy `{run_id}.json`.
