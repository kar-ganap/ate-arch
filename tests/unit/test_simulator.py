"""Tests for ate_arch.simulator — LLM-backed stakeholder simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ate_arch.models import (
    Constraint,
    ConstraintType,
    HiddenDependency,
    InterviewTurn,
    Stakeholder,
)
from ate_arch.simulator import (
    AnthropicLLMClient,
    SimulatorPool,
    StakeholderSimulator,
)

SCENARIO_ID = "scenario_b"

STAKEHOLDER_IDS = [
    "security_officer",
    "compliance_lead",
    "regional_ops_eu",
    "regional_ops_apac",
    "platform_architect",
    "product_manager",
]


# --- Test fixtures ---


class FakeLLMClient:
    """Fake LLM client for testing. Returns canned responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or ["Default stakeholder response."])
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": messages,
            }
        )
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response


@pytest.fixture
def security_officer() -> Stakeholder:
    """CSO with hard constraints, preferences, and a hidden dependency."""
    return Stakeholder(
        id="security_officer",
        name="Elena Vasquez",
        role="Chief Security Officer",
        constraints=[
            Constraint(
                id="HC-S1-1",
                description="All data encrypted at rest (AES-256) and in transit (TLS 1.3)",
                type=ConstraintType.HARD,
            ),
            Constraint(
                id="HC-S1-2",
                description="Zero-trust architecture",
                type=ConstraintType.HARD,
            ),
            Constraint(
                id="P-S1-1",
                description="Prefer single-vendor security stack",
                type=ConstraintType.PREFERENCE,
            ),
        ],
        hidden_dependencies=[
            HiddenDependency(
                id="HD1",
                description="Key rotation requires dual-key windows",
                trigger="asked about key rotation lifecycle",
                related_stakeholders=["platform_architect"],
            ),
        ],
    )


@pytest.fixture
def apac_ops() -> Stakeholder:
    """APAC ops with no hidden dependencies."""
    return Stakeholder(
        id="regional_ops_apac",
        name="Kenji Tanaka",
        role="Regional Operations Manager (APAC)",
        constraints=[
            Constraint(
                id="HC-S4-1",
                description="99.9% availability SLA for APAC",
                type=ConstraintType.HARD,
            ),
            Constraint(
                id="P-S4-1",
                description="Tokyo as primary APAC datacenter",
                type=ConstraintType.PREFERENCE,
            ),
        ],
        hidden_dependencies=[],
    )


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient(
        responses=[
            "As Security Officer, I require AES-256 encryption for all data at rest.",
            "I also require zero-trust architecture between all services.",
            "My preference is a single-vendor security stack.",
        ]
    )


# --- System Prompt Construction ---


class TestSystemPromptConstruction:
    def test_prompt_contains_stakeholder_name(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        assert "Elena Vasquez" in prompt

    def test_prompt_contains_role(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        assert "Chief Security Officer" in sim.system_prompt

    def test_prompt_contains_hard_constraints(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        assert "HC-S1-1" in prompt
        assert "AES-256" in prompt
        assert "HC-S1-2" in prompt
        assert "Zero-trust" in prompt

    def test_prompt_contains_preferences(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        assert "P-S1-1" in prompt
        assert "single-vendor" in prompt

    def test_prompt_contains_hidden_deps(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        assert "key rotation" in prompt.lower()
        assert "dual-key" in prompt.lower()
        assert "platform_architect" in prompt

    def test_prompt_omits_hidden_section_when_no_deps(
        self, apac_ops: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=apac_ops,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        # Should not contain hidden dependency section header
        assert "Additional Context" not in prompt

    def test_prompt_contains_guardrail_rules(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        prompt = sim.system_prompt
        # Check key guardrail instructions are present
        assert "volunteer" in prompt.lower()
        assert "other stakeholders" in prompt.lower()

    @pytest.mark.parametrize("stakeholder_id", STAKEHOLDER_IDS)
    def test_prompt_for_real_stakeholder(self, stakeholder_id: str) -> None:
        """Load each real stakeholder and verify prompt construction doesn't error."""
        from ate_arch.config import load_stakeholder

        stakeholder = load_stakeholder(SCENARIO_ID, stakeholder_id)
        fake = FakeLLMClient()
        sim = StakeholderSimulator(
            stakeholder=stakeholder,
            scenario_id=SCENARIO_ID,
            llm_client=fake,
        )
        prompt = sim.system_prompt
        assert stakeholder.name in prompt
        assert stakeholder.role in prompt
        # Every hard constraint ID should appear
        for c in stakeholder.constraints:
            if c.type == ConstraintType.HARD:
                assert c.id in prompt


# --- StakeholderSimulator ---


class TestStakeholderSimulator:
    def test_single_interview_returns_response(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        result = sim.interview("What are your encryption requirements?")
        assert result == "As Security Officer, I require AES-256 encryption for all data at rest."

    def test_interview_records_turn(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("What are your requirements?")
        assert sim.turn_count == 1

    def test_multi_turn_conversation(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        r1 = sim.interview("What are your encryption requirements?")
        r2 = sim.interview("What about network security?")
        assert r1 != r2  # Different canned responses
        assert sim.turn_count == 2

    def test_messages_include_history(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("First question")
        sim.interview("Second question")

        # The second call should include the first turn in messages
        second_call = fake_llm.calls[1]
        messages = second_call["messages"]
        assert len(messages) == 3  # Q1, A1, Q2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "First question"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["content"] == "Second question"

    def test_stakeholder_id_property(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        assert sim.stakeholder_id == "security_officer"

    def test_llm_called_with_correct_model(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            model="claude-haiku-4-5-20251001",
        )
        sim.interview("Test question")
        assert fake_llm.calls[0]["model"] == "claude-haiku-4-5-20251001"

    def test_llm_called_with_correct_temperature(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            temperature=0.1,
        )
        sim.interview("Test question")
        assert fake_llm.calls[0]["temperature"] == 0.1

    def test_llm_called_with_system_prompt(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Test question")
        assert fake_llm.calls[0]["system"] == sim.system_prompt

    def test_transcript_has_all_turns(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Q1")
        sim.interview("Q2")
        transcript = sim.get_transcript()
        assert transcript.turn_count == 2
        assert transcript.turns[0].question == "Q1"
        assert transcript.turns[1].question == "Q2"
        assert transcript.scenario_id == SCENARIO_ID
        assert transcript.stakeholder_id == "security_officer"

    def test_transcript_started_at_set_on_first_call(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Q1")
        transcript = sim.get_transcript()
        assert transcript.started_at is not None

    def test_transcript_completed_at_set(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Q1")
        transcript = sim.get_transcript()
        assert transcript.completed_at is not None

    def test_default_model(self, security_officer: Stakeholder, fake_llm: FakeLLMClient) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Test")
        # Default model should be passed to LLM
        assert fake_llm.calls[0]["model"] is not None

    def test_default_max_tokens(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        sim.interview("Test")
        assert fake_llm.calls[0]["max_tokens"] == 1024


# --- SimulatorPool ---


class TestSimulatorPool:
    def test_pool_creates_all_simulators(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
        )
        assert len(pool.stakeholder_ids) == 6
        assert set(pool.stakeholder_ids) == set(STAKEHOLDER_IDS)

    def test_pool_creates_subset(self, fake_llm: FakeLLMClient) -> None:
        subset = ["security_officer", "compliance_lead"]
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=subset,
        )
        assert len(pool.stakeholder_ids) == 2
        assert set(pool.stakeholder_ids) == set(subset)

    def test_interview_delegates_to_correct_simulator(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer", "compliance_lead"],
        )
        result = pool.interview("security_officer", "What are your requirements?")
        assert isinstance(result, str)
        # Verify the system prompt used was for security_officer
        assert "Elena Vasquez" in fake_llm.calls[0]["system"]

    def test_interview_unknown_stakeholder_raises(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer"],
        )
        with pytest.raises(KeyError, match="nonexistent"):
            pool.interview("nonexistent", "Hello?")

    def test_get_transcript(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer"],
        )
        pool.interview("security_officer", "Q1")
        transcript = pool.get_transcript("security_officer")
        assert transcript.turn_count == 1
        assert transcript.stakeholder_id == "security_officer"

    def test_get_transcript_unknown_raises(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer"],
        )
        with pytest.raises(KeyError, match="nonexistent"):
            pool.get_transcript("nonexistent")

    def test_get_all_transcripts(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer", "compliance_lead"],
        )
        pool.interview("security_officer", "Q1")
        transcripts = pool.get_all_transcripts()
        assert len(transcripts) == 2
        assert transcripts["security_officer"].turn_count == 1
        assert transcripts["compliance_lead"].turn_count == 0

    def test_stakeholder_ids_property(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer", "platform_architect"],
        )
        assert "security_officer" in pool.stakeholder_ids
        assert "platform_architect" in pool.stakeholder_ids

    def test_multi_turn_through_pool(self, fake_llm: FakeLLMClient) -> None:
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer"],
        )
        pool.interview("security_officer", "Q1")
        pool.interview("security_officer", "Q2")
        transcript = pool.get_transcript("security_officer")
        assert transcript.turn_count == 2


# --- Initial turns (state hydration) ---


class TestInitialTurns:
    def _make_prior_turns(self) -> list[InterviewTurn]:
        return [
            InterviewTurn(
                question="Prior Q1",
                response="Prior A1",
                turn_number=1,
                timestamp=datetime(2026, 2, 22, 10, 0, 0, tzinfo=UTC),
            ),
        ]

    def test_simulator_with_initial_turns(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        prior = self._make_prior_turns()
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            initial_turns=prior,
        )
        assert sim.turn_count == 1
        # New interview continues from turn 2
        sim.interview("Follow-up question")
        assert sim.turn_count == 2

    def test_initial_turns_included_in_messages(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        prior = self._make_prior_turns()
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            initial_turns=prior,
        )
        sim.interview("New question")
        # The LLM call should include prior history + new question
        messages = fake_llm.calls[0]["messages"]
        assert len(messages) == 3  # Prior Q1, Prior A1, New question
        assert messages[0]["content"] == "Prior Q1"
        assert messages[1]["content"] == "Prior A1"
        assert messages[2]["content"] == "New question"

    def test_transcript_from_hydrated_simulator(
        self, security_officer: Stakeholder, fake_llm: FakeLLMClient
    ) -> None:
        prior = self._make_prior_turns()
        sim = StakeholderSimulator(
            stakeholder=security_officer,
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            initial_turns=prior,
        )
        sim.interview("New Q")
        transcript = sim.get_transcript()
        assert transcript.turn_count == 2
        assert transcript.turns[0].question == "Prior Q1"
        assert transcript.turns[1].question == "New Q"

    def test_pool_with_initial_state(self, fake_llm: FakeLLMClient) -> None:
        prior = self._make_prior_turns()
        pool = SimulatorPool(
            scenario_id=SCENARIO_ID,
            llm_client=fake_llm,
            stakeholder_ids=["security_officer"],
            initial_state={"security_officer": prior},
        )
        # The pool should have the prior turn
        transcript = pool.get_transcript("security_officer")
        assert transcript.turn_count == 1
        # New interview continues
        pool.interview("security_officer", "Follow-up")
        transcript = pool.get_transcript("security_officer")
        assert transcript.turn_count == 2


# --- AnthropicLLMClient ---


class TestAnthropicLLMClient:
    def test_create_message_calls_sdk(self) -> None:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Mocked LLM response")]

        with patch("ate_arch.simulator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            client = AnthropicLLMClient()
            result = client.create_message(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                temperature=0.15,
                system="You are a stakeholder.",
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result == "Mocked LLM response"
            mock_client.messages.create.assert_called_once()

    def test_passes_all_params_to_sdk(self) -> None:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]

        with patch("ate_arch.simulator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            client = AnthropicLLMClient()
            client.create_message(
                model="test-model",
                max_tokens=512,
                temperature=0.2,
                system="System prompt",
                messages=[{"role": "user", "content": "Question"}],
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["max_tokens"] == 512
            assert call_kwargs["temperature"] == 0.2
            assert call_kwargs["system"] == "System prompt"
            assert call_kwargs["messages"] == [{"role": "user", "content": "Question"}]
