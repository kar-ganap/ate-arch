"""Pydantic data models for ate-arch."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator


class ConstraintType(StrEnum):
    """Type of stakeholder constraint."""

    HARD = "hard"
    PREFERENCE = "preference"


class Architecture(StrEnum):
    """Experimental architecture."""

    CONTROL = "control"  # Hub-and-spoke subagents
    TREATMENT = "treatment"  # Symmetric peers (Agent Teams)


class PartitionCondition(StrEnum):
    """Conflict partition condition."""

    A = "A"  # 100% within-partition
    B = "B"  # 50/50 within/cross
    C = "C"  # 100% cross-partition


class ResolutionQuality(StrEnum):
    """Quality of conflict resolution."""

    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    MISSING = "missing"


# Numeric scores for ResolutionQuality
RESOLUTION_SCORES: dict[ResolutionQuality, float] = {
    ResolutionQuality.OPTIMAL: 1.0,
    ResolutionQuality.ACCEPTABLE: 0.67,
    ResolutionQuality.POOR: 0.33,
    ResolutionQuality.MISSING: 0.0,
}


class Constraint(BaseModel):
    """A stakeholder constraint (hard requirement or preference)."""

    id: str
    description: str
    type: ConstraintType

    @field_validator("id")
    @classmethod
    def id_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "Constraint id must not be empty"
            raise ValueError(msg)
        return v


class HiddenDependency(BaseModel):
    """A non-obvious dependency between stakeholders, revealed only when asked."""

    id: str
    description: str
    trigger: str  # What question/topic reveals this dependency
    related_stakeholders: list[str]


class Stakeholder(BaseModel):
    """A stakeholder with constraints and hidden dependencies."""

    id: str
    name: str
    role: str
    constraints: list[Constraint]
    hidden_dependencies: list[HiddenDependency]


class Conflict(BaseModel):
    """A conflict between two stakeholders' constraints."""

    id: str
    description: str
    stakeholder_a: str
    constraint_a: str
    stakeholder_b: str
    constraint_b: str
    optimal_resolution: str
    acceptable_resolutions: list[str]


class Scenario(BaseModel):
    """A scenario definition (e.g., multi-region data platform)."""

    id: str
    name: str
    description: str
    stakeholder_ids: list[str]
    conflict_ids: list[str]
    hidden_dependency_count: int


class Partition(BaseModel):
    """A partition assignment for a given condition."""

    condition: PartitionCondition
    agent_1_stakeholders: list[str]
    agent_2_stakeholders: list[str]
    within_partition_conflicts: list[str]
    cross_partition_conflicts: list[str]


class MessageRole(StrEnum):
    """Role in a stakeholder interview conversation."""

    USER = "user"
    ASSISTANT = "assistant"


class InterviewMessage(BaseModel):
    """A single message in a stakeholder interview."""

    role: MessageRole
    content: str
    timestamp: datetime

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "Message content must not be empty"
            raise ValueError(msg)
        return v


class InterviewTurn(BaseModel):
    """A question-response pair in an interview."""

    question: str
    response: str
    turn_number: int
    timestamp: datetime


class InterviewTranscript(BaseModel):
    """Complete transcript of all interviews with a single stakeholder."""

    scenario_id: str
    stakeholder_id: str
    turns: list[InterviewTurn]
    started_at: datetime
    completed_at: datetime | None = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def to_messages(self) -> list[InterviewMessage]:
        """Flatten turns into a chronological message list."""
        messages: list[InterviewMessage] = []
        for turn in self.turns:
            messages.append(
                InterviewMessage(
                    role=MessageRole.USER,
                    content=turn.question,
                    timestamp=turn.timestamp,
                )
            )
            messages.append(
                InterviewMessage(
                    role=MessageRole.ASSISTANT,
                    content=turn.response,
                    timestamp=turn.timestamp,
                )
            )
        return messages


class RubricWeights(BaseModel):
    """Weights for the 4-layer rubric composite score."""

    l1: float = 0.25
    l2: float = 0.25
    l3: float = 0.30
    l4: float = 0.20


class RunResult(BaseModel):
    """Scored result of a single experimental run."""

    run_id: str
    architecture: Architecture
    partition_condition: PartitionCondition
    l1_constraint_discovery: float  # 0.0-1.0
    l2_conflict_identification: float  # 0.0-1.0
    l3_conflict_resolution: dict[str, ResolutionQuality]  # conflict_id -> quality
    l4_hidden_dependencies: float  # 0.0-1.0

    def l3_score(self) -> float:
        """Compute aggregate L3 score from per-conflict resolution qualities."""
        if not self.l3_conflict_resolution:
            return 0.0
        total = sum(RESOLUTION_SCORES[q] for q in self.l3_conflict_resolution.values())
        return total / len(self.l3_conflict_resolution)

    def composite_score(self, weights: RubricWeights) -> float:
        """Compute weighted composite score across all 4 rubric layers."""
        return (
            weights.l1 * self.l1_constraint_discovery
            + weights.l2 * self.l2_conflict_identification
            + weights.l3 * self.l3_score()
            + weights.l4 * self.l4_hidden_dependencies
        )


class RunMetadata(BaseModel):
    """Metadata for a single experimental run."""

    run_id: str
    architecture: Architecture
    partition_condition: PartitionCondition
    claude_code_version: str
    model: str
    started_at: datetime
    wall_clock_minutes: float
    token_count: int | None = None
    interview_count: int | None = None
    notes: str | None = None
