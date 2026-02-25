# Phase 6 Plan: Execution

## Context

Phase 5 is complete and merged. Pipeline validated end-to-end with 4 pilot
runs. Key findings: L1/L2 ceiling at 1.00, zero peer-to-peer SendMessage,
indirect collaboration through shared file I/O observed but not tracked.

## Deliverables

### 1. Indirect Collaboration Tracking (`comms.py`)

New models: `FileOperation`, `IndirectCollaboration`. Track Read/Edit/Write
operations on shared files with agent attribution. Boolean signal +
chronological sequence log.

Agent attribution: coordinator-level from `type=assistant`, subagent from
`type=progress` entries with `data.agentId`.

### 2. Lead Relay Transparency Metric (`comms.py`)

New models: `RelayEvent`, `RelayAnalysis`. Measure how much the lead agent
transforms information when relaying between agents. Uses
`difflib.SequenceMatcher.ratio()` (stdlib, no new deps).

### 3. Communication Summary Persistence

Save/load `CommunicationSummary` to `data/comms/{run_id}_comms.json`.

### 4. `postprocess` CLI Command

Single command chaining: update-metadata, score, analyze-comms.

### 5. Enhanced `list-runs` Command

Show scored/complete/scaffolded status with composite scores.

### 6. Retroactive Pilot Analysis

Re-run analysis on all 4 pilot transcripts.

### 7. Live Execution (16 new runs)

4 runs each for control-A, treatment-A, control-C, treatment-C (runs 2-5).

## Implementation Order

TDD: tests before code for all deliverables.

## Acceptance Criteria

- `make test` passes (~297 tests)
- `make lint` clean
- `make typecheck` clean
- New CLI commands functional
- Comms summaries persisted for all runs
