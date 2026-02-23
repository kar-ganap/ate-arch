# Phase 1 Retro: Scenario Design

## What Worked

- Conflict graph analysis up front — mapping all 8 conflicts as edges between
  stakeholder nodes made partition math tractable and revealed that 100/0 splits
  are impossible with this graph structure.
- TDD cycle worked smoothly: 34 new tests written first, all passed on first
  implementation pass.
- Stakeholder constraint sheets are thematically coherent — each hidden
  dependency has a realistic trigger and the conflicts arise naturally from
  competing priorities (security vs performance, compliance vs operations).
- Parametrized tests for all 6 stakeholders caught a YAML formatting issue
  early.

## Surprises

- **Partition math constraints**: The idealized 100/0 and 0/100 within/cross
  splits turned out to be mathematically impossible for any single conflict
  graph with 8 edges and 3+3 partitions. The achievable gradient is 75/25 →
  50/50 → 25/75. This required updating the experiment design doc.
- The 3x increase in cross-partition conflicts (2 → 6 from condition A to C)
  should still provide sufficient signal, but it's less dramatic than originally
  planned.

## Deviations from Plan

- No `GroundTruth` Pydantic model was created — ground truth is loaded as raw
  YAML since it's only consumed by scoring (Phase 4). Added `load_ground_truth()`
  was not needed either since the structure doesn't match any existing model
  cleanly.
- `ConflictSet` and `PartitionSet` wrapper models mentioned in the plan were
  not created — the list-based loaders (`load_conflicts()`, `load_partitions()`)
  are sufficient.

## Implicit Assumptions Made Explicit

- Conflict graph structure determines partition options — this wasn't obvious at
  planning time but is now documented in experiment-design.md.
- Hidden dependencies are one-directional (source stakeholder knows, target
  doesn't) — this is by design to create information asymmetry.
- Acceptable resolutions satisfy hard constraints but trade off preferences —
  this distinction matters for L3 scoring.

## Scope Changes for Next Phase

- Phase 2 (Simulator) can proceed as planned — no scenario changes needed.
- Model choice for stakeholder simulation left open (Haiku vs Sonnet vs Opus).

## Metrics

- Tests added: 34 (49 total)
- Files created: 12 (6 stakeholder YAMLs, scenario, conflicts, partitions,
  ground truth, test_config.py, phase-1-plan.md)
- Files modified: 3 (config.py, experiment-design.md, CLAUDE.md)
