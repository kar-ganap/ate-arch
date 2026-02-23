"""LLM-backed stakeholder simulation for architecture design interviews."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import anthropic

from ate_arch.config import load_all_stakeholders, load_stakeholder
from ate_arch.models import (
    ConstraintType,
    InterviewTranscript,
    InterviewTurn,
    Stakeholder,
)

# --- System prompt templates ---

_SYSTEM_PROMPT_TEMPLATE = """You are {name}, the {role} at DataFlow Corp.

You are being interviewed about your requirements for the Multi-Region Data \
Platform project. Answer questions based ONLY on the information below.

## Your Requirements

### Hard Constraints (non-negotiable)
{hard_constraints}

### Preferences (negotiable but desired)
{preferences}
{hidden_deps_section}
## Rules of Engagement

1. ONLY discuss YOUR requirements listed above. Never volunteer information unless directly asked.
2. Answer concisely and factually. Do not elaborate beyond what was asked.
3. If asked about topics not covered by your requirements, say you don't have a strong \
opinion or defer to the relevant stakeholder.
4. NEVER reveal or hint at other stakeholders' constraints. You only know your own.
5. NEVER mention the existence of "hidden dependencies" or "triggers". If the trigger \
condition is met by the interviewer's question, naturally reveal the information as if \
it's something you just thought of.
6. You may express firmness about your hard constraints — they are non-negotiable for you.
7. For preferences, you can indicate flexibility if pressed.
8. Do not invent requirements beyond what is listed above."""

_HIDDEN_DEP_SECTION_TEMPLATE = """
## Additional Context (reveal ONLY when triggered)

{hidden_deps}

For each item above, ONLY share this information if the interviewer's question \
specifically relates to the trigger topic. When you do reveal it, present it \
naturally as a concern or consideration — never as a scripted response.
"""


# --- LLM client protocol + implementation ---


class LLMClient(Protocol):
    """Protocol for LLM API calls — enables dependency injection for testing."""

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str,
        messages: list[dict[str, str]],
    ) -> str: ...


class AnthropicLLMClient:
    """Real LLM client wrapping the Anthropic Messages API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        )
        block = response.content[0]
        assert hasattr(block, "text"), f"Expected TextBlock, got {type(block).__name__}"
        return block.text


# --- Stakeholder simulator ---


class StakeholderSimulator:
    """Simulates a single stakeholder backed by an LLM."""

    def __init__(
        self,
        stakeholder: Stakeholder,
        scenario_id: str,
        llm_client: LLMClient,
        model: str = "claude-haiku-4-5-20251001",
        temperature: float = 0.15,
        max_tokens: int = 1024,
    ) -> None:
        self._stakeholder = stakeholder
        self._scenario_id = scenario_id
        self._llm_client = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = self._build_system_prompt()
        self._turns: list[InterviewTurn] = []
        self._started_at: datetime | None = None

    @property
    def stakeholder_id(self) -> str:
        return self._stakeholder.id

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def interview(self, questions: str) -> str:
        """Ask the stakeholder questions. Returns their response."""
        if self._started_at is None:
            self._started_at = datetime.now(UTC)

        messages = self._build_messages(questions)

        response = self._llm_client.create_message(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=self._system_prompt,
            messages=messages,
        )

        now = datetime.now(UTC)
        turn = InterviewTurn(
            question=questions,
            response=response,
            turn_number=len(self._turns) + 1,
            timestamp=now,
        )
        self._turns.append(turn)

        return response

    def get_transcript(self) -> InterviewTranscript:
        """Return a snapshot of the full interview transcript."""
        return InterviewTranscript(
            scenario_id=self._scenario_id,
            stakeholder_id=self._stakeholder.id,
            turns=list(self._turns),
            started_at=self._started_at or datetime.now(UTC),
            completed_at=datetime.now(UTC) if self._turns else None,
        )

    def _build_system_prompt(self) -> str:
        """Construct the system prompt from the stakeholder's constraint sheet."""
        hard = [c for c in self._stakeholder.constraints if c.type == ConstraintType.HARD]
        prefs = [c for c in self._stakeholder.constraints if c.type == ConstraintType.PREFERENCE]

        hard_text = "\n".join(f"- [{c.id}] {c.description}" for c in hard)
        pref_text = "\n".join(f"- [{c.id}] {c.description}" for c in prefs)

        hidden_section = ""
        if self._stakeholder.hidden_dependencies:
            deps_text = "\n".join(
                f"- Topic: {hd.trigger}\n"
                f"  Concern: {hd.description}\n"
                f"  This affects: {', '.join(hd.related_stakeholders)}"
                for hd in self._stakeholder.hidden_dependencies
            )
            hidden_section = _HIDDEN_DEP_SECTION_TEMPLATE.format(hidden_deps=deps_text)

        return _SYSTEM_PROMPT_TEMPLATE.format(
            name=self._stakeholder.name,
            role=self._stakeholder.role,
            hard_constraints=hard_text,
            preferences=pref_text,
            hidden_deps_section=hidden_section,
        )

    def _build_messages(self, new_question: str) -> list[dict[str, str]]:
        """Build the full message array including conversation history."""
        messages: list[dict[str, str]] = []
        for turn in self._turns:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant", "content": turn.response})
        messages.append({"role": "user", "content": new_question})
        return messages


# --- Simulator pool ---


class SimulatorPool:
    """Pool of stakeholder simulators for a scenario."""

    def __init__(
        self,
        scenario_id: str,
        llm_client: LLMClient,
        model: str = "claude-haiku-4-5-20251001",
        temperature: float = 0.15,
        max_tokens: int = 1024,
        stakeholder_ids: list[str] | None = None,
    ) -> None:
        if stakeholder_ids is not None:
            stakeholders = [load_stakeholder(scenario_id, sid) for sid in stakeholder_ids]
        else:
            stakeholders = load_all_stakeholders(scenario_id)

        self._simulators: dict[str, StakeholderSimulator] = {}
        for s in stakeholders:
            self._simulators[s.id] = StakeholderSimulator(
                stakeholder=s,
                scenario_id=scenario_id,
                llm_client=llm_client,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    @property
    def stakeholder_ids(self) -> list[str]:
        return list(self._simulators.keys())

    def interview(self, stakeholder_id: str, questions: str) -> str:
        """Interview a specific stakeholder. Raises KeyError if not in pool."""
        if stakeholder_id not in self._simulators:
            msg = (
                f"Stakeholder '{stakeholder_id}' not in pool. "
                f"Available: {list(self._simulators.keys())}"
            )
            raise KeyError(msg)
        return self._simulators[stakeholder_id].interview(questions)

    def get_transcript(self, stakeholder_id: str) -> InterviewTranscript:
        """Get transcript for a specific stakeholder."""
        if stakeholder_id not in self._simulators:
            msg = f"Stakeholder '{stakeholder_id}' not in pool"
            raise KeyError(msg)
        return self._simulators[stakeholder_id].get_transcript()

    def get_all_transcripts(self) -> dict[str, InterviewTranscript]:
        """Get transcripts for all stakeholders."""
        return {sid: sim.get_transcript() for sid, sim in self._simulators.items()}
