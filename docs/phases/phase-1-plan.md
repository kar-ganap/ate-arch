# Phase 1: Scenario Design

## Goal

Define Scenario B (Multi-Region Data Platform) — the concrete content that
drives the entire experiment.

## Deliverables

- 6 stakeholder constraint sheets (YAML)
- 8 conflicts with optimal + acceptable resolutions
- 4 hidden dependencies with triggers
- 3 partition configurations (A, B, C)
- Ground truth reference architecture
- Config loaders for all new YAML files
- 34 new unit tests (49 total)

## Partition Math

With 8 conflicts among 6 stakeholders in 3+3 partitions, the achievable
within/cross gradient is 75% → 50% → 25% (not the idealized 100/0/0-100).
The conflict graph forms two natural clusters connected by 2 bridge conflicts.

## Acceptance Criteria

- `make test` passes (49 tests)
- `make lint` clean
- `make typecheck` clean
- All config files load and validate through Pydantic models
- Partition within/cross counts match expected ratios
- Every conflict references valid stakeholders
- Every hidden dependency has a trigger and related stakeholders
