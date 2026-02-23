# Phase 5: Pilot

## Goal

Build batch operations tooling (scaffolding, verification, communication
analysis) and validate the full pipeline end-to-end with 3 live pilot runs.

## Deliverables

- `batch.py` module: batch_scaffold(), verify_run_structural(),
  verify_run_complete() with VerificationIssue/VerificationReport models
- `comms.py` module: parse_jsonl_file(), extract_peer_messages(),
  analyze_session() with PeerMessage/CommunicationSummary models
- 3 CLI commands: batch-scaffold, verify-run, analyze-comms
- Execution guide (docs/execution-guide.md)
- .gitignore fix for data/runs/*
- ~45 new unit tests (251 total), all mocked
- 3 live pilot runs: control-A-1, treatment-A-1, control-C-1

## Key Design Decisions

- Communication analysis: only SendMessage/message_peer tool calls count as
  peer communication (same pattern as ate experiment)
- Verification is two-stage: structural (pre-run file checks) and complete
  (post-run artifact validation)
- batch_scaffold() delegates to existing scaffold_run() — no duplication

## Acceptance Criteria

- `make test` passes (~251 tests)
- `make lint` clean
- `make typecheck` clean
- `ate-arch batch-scaffold` creates all 30 run directories
- `ate-arch verify-run` catches missing/empty files
- `ate-arch analyze-comms` parses JSONL and reports peer messages
- 3 pilot runs complete end-to-end (scaffold → interview → score)
