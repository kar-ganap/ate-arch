# Phase 3 Retro: Execution Harness

## What Worked

- CLI-per-invocation design is clean and testable. No server process, no
  background state — each `ate-arch interview` reads JSON, interviews, writes
  JSON. The agent just reads stdout.
- `initial_turns` parameter on StakeholderSimulator is backward-compatible.
  Existing tests unaffected, 4 new tests validate hydration behavior.
- Session guides are fully self-contained: copy-paste the opening prompt, follow
  the checklist, update metadata when done. Human operator needs no other docs.
- Scaffold is idempotent and non-destructive: `notes.md` preserved on
  re-scaffold, metadata.json and session_guide.md overwritten.

## Surprises

- `RunMetadata.started_at` was initially a required `datetime` field. Scaffold
  needs to create a template with `None` — had to make it `datetime | None = None`
  with defaults on other fields too.
- CLI test mocking was tricky for the `interview` command. `load_stakeholder`,
  `AnthropicLLMClient`, and `StakeholderSimulator` are imported inside the
  function body (lazy imports to avoid heavy imports on every CLI invocation).
  Must patch at source module (`ate_arch.config.load_stakeholder`,
  `ate_arch.simulator.AnthropicLLMClient`) not at `ate_arch.cli.*`.
- Typer's `Optional[X]` annotations trigger ruff UP045 (prefer `X | None`).
  Typer actually needs `Optional` for its type introspection in older versions,
  but current version handles `X | None` fine.

## Deviations from Plan

- Plan estimated ~35 new tests, actual is 45 (34 harness + 7 CLI + 4
  simulator). More thorough prompt content tests than initially scoped.
- `save_interview_state` takes `dict[str, list[InterviewTurn]]` not
  `dict[str, InterviewTranscript]` — simpler serialization, the transcript
  wrapper is unnecessary for state persistence.
- No partition enforcement in CLI — the prompt tells agents which stakeholders
  are theirs. Wrong-stakeholder interviews are a detectable protocol violation,
  not a harness error.

## Implicit Assumptions Made Explicit

- Run IDs are deterministic (`control-A-1`) not UUIDs — human-readable and easy
  to reference in analysis scripts.
- `SCENARIO_ID = "scenario_b"` is hardcoded in the harness module. Only one
  scenario exists and the experiment design calls for exactly one.
- The control prompt forbids the lead from interviewing directly (must delegate
  via Task tool). This is enforced by prompt instructions, not code.

## Scope Changes for Next Phase

- Phase 4 (Rubric/Scoring) will consume the architecture documents produced by
  agents. Need LLM-based scoring for L3 (conflict resolution quality) and
  potentially L1/L2/L4 if keyword matching proves insufficient.
- Preflight checks for architecture-specific env vars
  (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) are in the CLI but not yet tested
  end-to-end with real Claude Code sessions.

## Metrics

- Tests added: 45 (143 total)
- Files created: 3 (harness.py, test_harness.py, test_cli.py)
- Files modified: 4 (cli.py, models.py, simulator.py, test_simulator.py)
- Dependencies added: 0
