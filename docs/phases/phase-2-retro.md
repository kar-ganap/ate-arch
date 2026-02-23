# Phase 2 Retro: Stakeholder Simulator

## What Worked

- Protocol-based DI for the LLM client made testing trivial — `FakeLLMClient`
  with canned responses let us test all simulator logic without any real API
  calls.
- System prompt construction is fully deterministic and testable. Parametrized
  test across all 6 real stakeholders catches any YAML/model mismatches.
- TDD cycle clean: 49 new tests written first, all passed on first
  implementation.
- `SimulatorPool` abstraction cleanly separates routing from simulation logic.

## Surprises

- mypy strict mode accepted the `LLMClient` Protocol without issues — no
  `type: ignore` needed for the protocol itself. One `type: ignore[arg-type]`
  was needed in `AnthropicLLMClient` for the messages parameter (Anthropic SDK
  types are stricter than `list[dict[str, str]]`). A second `type: ignore` for
  `block.text` turned out to be unnecessary.
- `anthropic>=0.52` pulled in 12 transitive dependencies (httpx, anyio, etc.)
  — expected but notable for the dependency footprint.
- ruff format caught trailing whitespace in the prompt templates with line
  continuations.

## Deviations from Plan

- Plan estimated ~45 new tests, actual is 49 (12 model + 37 simulator). Slight
  overcount on model tests (added `test_turn_number_positive` and
  `test_completed_at` not originally planned).
- Default model set to `claude-haiku-4-5-20251001` instead of
  `claude-opus-4-6` — Haiku is more appropriate for stakeholder simulation
  (script-following at low temperature). Model is configurable via constructor.
- No separate `config/prompts/` directory or `config/llm.yaml` — system prompt
  is built in code (closely coupled to Stakeholder model), and LLM config is
  constructor parameters. Simpler than template files.

## Implicit Assumptions Made Explicit

- Hidden dependency triggering is handled entirely by the LLM via system prompt
  instructions — no code-level trigger matching. This relies on low temperature
  (0.15) for reliable adherence.
- No `reset()` method on simulators — each experimental run creates a fresh
  `SimulatorPool`. This matches experiment design §9 ("each run is
  self-contained").
- Conversation history grows unboundedly within a single stakeholder interview.
  At 3-5 turns per stakeholder, this is well within token limits.

## Scope Changes for Next Phase

- Phase 3 (Harness) will consume `SimulatorPool.interview()` as the tool the
  agent calls. Need to design the tool interface (Claude Code tool definition)
  and the run lifecycle.
- `InterviewTranscript` serialization to disk (for raw data preservation) is a
  Phase 3 concern, not Phase 2.

## Metrics

- Tests added: 49 (98 total)
- Files created: 3 (simulator.py, test_simulator.py, phase-2-plan.md)
- Files modified: 3 (models.py, test_models.py, pyproject.toml)
- Dependencies added: 1 (anthropic>=0.52, 12 transitive)
