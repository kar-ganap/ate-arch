# Phase 4 Retro: Rubric Scoring

## What Worked

- All 4 scoring layers implemented and tested in one pass — 56 scoring tests
  passed on first implementation run, zero debugging needed.
- FakeLLMClient pattern from Phase 2 transferred cleanly. Scoring tests use
  the same canned-response pattern with call recording for prompt verification.
- Response parser design (prefix-match with conservative fallback) is simple
  and robust. Unparseable responses default to NOT_FOUND/MISSING, which is the
  safe conservative direction.
- Pydantic's ConfigDict(frozen=True) for scoring models ensures immutability
  of results after creation.
- One LLM call per item (constraint/conflict/dependency) keeps prompts focused
  and makes individual failures easy to diagnose.

## Surprises

- `RunResult.composite_score()` requires a `RubricWeights` argument (no default
  in signature). The CLI score command needed an explicit `RubricWeights()`
  call. This is actually good design — weights should be explicit — but caught
  by mypy, not at test time.
- The ruff import sorter caught test_scoring.py imports on the first lint run.
  Consistent pattern: ruff format + ruff check --fix handles these
  automatically.
- Temperature discussion led to a valuable design insight: temp=0.0 (greedy
  decoding) defeats the purpose of LLM-based scoring over keyword matching.
  Settled on 0.3 as the sweet spot — low enough for consistency, high enough
  for flexible reasoning.

## Deviations from Plan

- Plan estimated ~60 new tests, actual is 63 (56 scoring + 5 config + 2 CLI).
  Slight overcount from additional parsing edge case tests.
- No separate `GroundTruth` model needed — the conflict definitions already
  contain `optimal_resolution` and `acceptable_resolutions`. Ground truth YAML
  is for analysis reference, not consumed by the scoring module.
- `ScoringResult` includes both aggregate conversion (`to_run_result()`) and
  detailed persistence (`save_scoring_detail()`). Plan only mentioned RunResult
  persistence; the detail file preserves per-item evidence and reasoning for
  debugging.

## Implicit Assumptions Made Explicit

- Architecture documents fit in a single LLM context window. At ~10K tokens
  for a typical architecture doc, this is well within limits. No chunking
  needed.
- LLM scoring is done once per document (no retry/average). If consistency is
  a concern, Phase 5 pilot will reveal it.
- 23 hard constraints (not 24 as some docs state). 4+4+3+4+4+4 = 23. Scoring
  counts dynamically from loaded config.
- Model choice is configurable via CLI flag. Default is Haiku for speed/cost.
  Can upgrade to Sonnet/Opus for L3 if pilot shows quality issues.

## Scope Changes for Next Phase

- Phase 5 (Pilot) will run 2-3 experimental runs end-to-end, including scoring.
  This will validate whether Haiku produces reliable scoring judgments or if L3
  needs a more capable model.
- The `score` CLI command parses run_id to extract architecture/partition. This
  works but is fragile — if run ID format changes, parsing breaks. Acceptable
  for now since the format is deterministic.

## Metrics

- Tests added: 63 (206 total)
- Files created: 3 (scoring.py, test_scoring.py, rubric.yaml)
- Files modified: 4 (config.py, test_config.py, cli.py, test_cli.py)
- Dependencies added: 0
