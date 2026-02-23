# Phase 3: Execution Harness

## Goal

Build the scaffolding and runtime support for the 30 experimental runs. Two
jobs: (1) pre-run scaffolding (directories, prompts, session guides) and (2)
runtime support (`ate-arch interview` CLI command agents call during sessions).

## Deliverables

- `harness.py` module with run ID generation, directory scaffolding, prompt
  generation, session guide rendering, preflight checks, metadata/state
  persistence
- CLI expansion: `scaffold`, `interview`, `preflight`, `update-metadata`,
  `list-runs` commands
- Simulator modifications: `initial_turns` on `StakeholderSimulator`,
  `initial_state` on `SimulatorPool` for conversation state hydration
- 45 new unit tests (143 total), all mocked

## Key Design Decision

CLI-per-invocation for interviews (not a server). Each `ate-arch interview`
call reads state from JSON, creates a fresh simulator with history, calls the
LLM, saves updated state, and prints the response to stdout. File-based state
handles multi-turn conversations without a background process.

## Acceptance Criteria

- `make test` passes (143 tests)
- `make lint` clean
- `make typecheck` clean
- `ate-arch scaffold` creates correct directory structure
- `ate-arch interview` calls simulator with state persistence
- `ate-arch preflight` validates environment
- Opening prompts contain correct instructions per architecture
- Session guides are copy-paste ready for running experiments
- No real LLM calls in any test
