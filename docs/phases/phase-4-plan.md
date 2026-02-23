# Phase 4: Rubric Scoring

## Goal

Build the 4-layer rubric scoring module that evaluates architecture documents
produced by agents against ground truth using LLM-based semantic matching.

## Deliverables

- `scoring.py` module with L1 (constraint discovery), L2 (conflict
  identification), L3 (conflict resolution quality), L4 (hidden dependency
  discovery) scoring functions, orchestrator, and persistence
- 5 Pydantic models: ConstraintMatch, ConflictMatch, ResolutionJudgment,
  DependencyMatch, ScoringResult
- LLM prompt templates for all 4 scoring layers
- Response parsers for FOUND/NOT_FOUND and OPTIMAL/ACCEPTABLE/POOR/MISSING
- Config helpers: `load_all_hard_constraints`, `load_all_hidden_dependencies`
- CLI `score` command
- `config/rubric.yaml` documenting weights and approach
- 63 new unit tests (206 total), all mocked via FakeLLMClient

## Key Design Decision

All 4 layers use LLM-based semantic matching (not keyword matching). Agents
paraphrase constraints in free-form markdown — keyword matching would produce
false negatives. Temperature set to 0.3 (not 0.0) to allow flexible reasoning
while maintaining consistency.

## Acceptance Criteria

- `make test` passes (206 tests)
- `make lint` clean
- `make typecheck` clean
- All 4 scoring layers produce correct results with FakeLLMClient
- LLM prompts contain constraint/conflict/dependency definitions and document
- ScoringResult aggregates to RunResult with correct composite scores
- `ate-arch score` CLI command works end-to-end (mocked)
- No real LLM calls in any test
