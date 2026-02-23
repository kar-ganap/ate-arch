# Phase 2: Stakeholder Simulator

## Goal

Build the LLM-backed stakeholder simulation module — each stakeholder is
simulated by an LLM with a system prompt constructed from their private
constraint sheet.

## Deliverables

- `StakeholderSimulator` class (single stakeholder, system prompt + conversation history)
- `SimulatorPool` class (routes interviews to correct simulator)
- `LLMClient` protocol + `AnthropicLLMClient` implementation
- System prompt template with guardrails (no volunteering, no leaking, trigger-based hidden deps)
- 4 new Pydantic models (MessageRole, InterviewMessage, InterviewTurn, InterviewTranscript)
- 49 new unit tests (98 total), all mocked via FakeLLMClient
- `anthropic>=0.52` dependency

## Acceptance Criteria

- `make test` passes (98 tests)
- `make lint` clean
- `make typecheck` clean
- System prompts correct for all 6 stakeholders (parametrized test)
- Multi-turn conversation history correctly passed to LLM
- SimulatorPool routes to correct stakeholder
- InterviewTranscript captures all turns with timestamps
- No real LLM calls in any test
