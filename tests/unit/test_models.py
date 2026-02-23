"""Tests for ate_arch.models — Pydantic data models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ate_arch.models import (
    Architecture,
    Conflict,
    Constraint,
    ConstraintType,
    HiddenDependency,
    Partition,
    PartitionCondition,
    ResolutionQuality,
    RubricWeights,
    RunMetadata,
    RunResult,
    Scenario,
    Stakeholder,
)

# --- Constraint ---


class TestConstraint:
    def test_hard_constraint(self) -> None:
        c = Constraint(
            id="c1", description="Data must be encrypted at rest", type=ConstraintType.HARD
        )
        assert c.id == "c1"
        assert c.type == ConstraintType.HARD

    def test_preference_constraint(self) -> None:
        c = Constraint(id="c2", description="Prefer PostgreSQL", type=ConstraintType.PREFERENCE)
        assert c.type == ConstraintType.PREFERENCE

    def test_constraint_requires_id(self) -> None:
        with pytest.raises(ValidationError):
            Constraint(id="", description="test", type=ConstraintType.HARD)


# --- Stakeholder ---


class TestStakeholder:
    def test_stakeholder_creation(self) -> None:
        s = Stakeholder(
            id="security_officer",
            name="Security Officer",
            role="Head of Information Security",
            constraints=[
                Constraint(
                    id="sec1",
                    description="All data encrypted at rest",
                    type=ConstraintType.HARD,
                ),
            ],
            hidden_dependencies=[],
        )
        assert s.id == "security_officer"
        assert len(s.constraints) == 1

    def test_stakeholder_with_hidden_dependencies(self) -> None:
        s = Stakeholder(
            id="compliance_lead",
            name="Compliance Lead",
            role="Regulatory Compliance",
            constraints=[
                Constraint(
                    id="comp1",
                    description="GDPR compliance required",
                    type=ConstraintType.HARD,
                ),
            ],
            hidden_dependencies=[
                HiddenDependency(
                    id="hd1",
                    description="GDPR requires data residency in EU",
                    trigger="asked about data storage location",
                    related_stakeholders=["regional_ops_eu"],
                ),
            ],
        )
        assert len(s.hidden_dependencies) == 1
        assert s.hidden_dependencies[0].trigger == "asked about data storage location"


# --- Conflict ---


class TestConflict:
    def test_conflict_creation(self) -> None:
        c = Conflict(
            id="conflict1",
            description="Encryption at rest vs performance requirements",
            stakeholder_a="security_officer",
            constraint_a="sec1",
            stakeholder_b="platform_architect",
            constraint_b="perf1",
            optimal_resolution="Use hardware-accelerated encryption",
            acceptable_resolutions=["Use application-level encryption with caching"],
        )
        assert c.stakeholder_a == "security_officer"
        assert c.stakeholder_b == "platform_architect"
        assert len(c.acceptable_resolutions) == 1


# --- Scenario ---


class TestScenario:
    def test_scenario_creation(self) -> None:
        s = Scenario(
            id="scenario_b",
            name="Multi-Region Data Platform",
            description="A company needs a data platform spanning 3 geographic regions",
            stakeholder_ids=["s1", "s2", "s3", "s4", "s5", "s6"],
            conflict_ids=["c1", "c2", "c3"],
            hidden_dependency_count=4,
        )
        assert s.id == "scenario_b"
        assert len(s.stakeholder_ids) == 6


# --- Partition ---


class TestPartition:
    def test_partition_condition_a(self) -> None:
        p = Partition(
            condition=PartitionCondition.A,
            agent_1_stakeholders=["s1", "s2", "s3"],
            agent_2_stakeholders=["s4", "s5", "s6"],
            within_partition_conflicts=["c1", "c2", "c3"],
            cross_partition_conflicts=[],
        )
        assert p.condition == PartitionCondition.A
        assert len(p.cross_partition_conflicts) == 0

    def test_partition_condition_c(self) -> None:
        p = Partition(
            condition=PartitionCondition.C,
            agent_1_stakeholders=["s1", "s2", "s3"],
            agent_2_stakeholders=["s4", "s5", "s6"],
            within_partition_conflicts=[],
            cross_partition_conflicts=["c1", "c2", "c3"],
        )
        assert p.condition == PartitionCondition.C
        assert len(p.within_partition_conflicts) == 0


# --- RunResult ---


class TestRunResult:
    def test_run_result_creation(self) -> None:
        r = RunResult(
            run_id="control-a-1",
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
            l1_constraint_discovery=0.75,
            l2_conflict_identification=0.80,
            l3_conflict_resolution={
                "c1": ResolutionQuality.OPTIMAL,
                "c2": ResolutionQuality.ACCEPTABLE,
            },
            l4_hidden_dependencies=0.50,
        )
        assert r.run_id == "control-a-1"
        assert r.architecture == Architecture.CONTROL
        assert r.l3_conflict_resolution["c1"] == ResolutionQuality.OPTIMAL

    def test_composite_score(self) -> None:
        r = RunResult(
            run_id="treatment-b-3",
            architecture=Architecture.TREATMENT,
            partition_condition=PartitionCondition.B,
            l1_constraint_discovery=0.80,
            l2_conflict_identification=1.0,
            l3_conflict_resolution={
                "c1": ResolutionQuality.OPTIMAL,
                "c2": ResolutionQuality.OPTIMAL,
                "c3": ResolutionQuality.ACCEPTABLE,
            },
            l4_hidden_dependencies=0.75,
        )
        weights = RubricWeights()
        score = r.composite_score(weights)
        # L3 score: optimal=1.0, acceptable=0.67 → (1.0+1.0+0.67)/3 = 0.89
        expected_l3 = (1.0 + 1.0 + 0.67) / 3
        expected = 0.25 * 0.80 + 0.25 * 1.0 + 0.30 * expected_l3 + 0.20 * 0.75
        assert abs(score - expected) < 0.01

    def test_composite_score_empty_l3(self) -> None:
        r = RunResult(
            run_id="control-c-5",
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.C,
            l1_constraint_discovery=0.50,
            l2_conflict_identification=0.50,
            l3_conflict_resolution={},
            l4_hidden_dependencies=0.25,
        )
        weights = RubricWeights()
        score = r.composite_score(weights)
        # Empty L3 → 0.0
        expected = 0.25 * 0.50 + 0.25 * 0.50 + 0.30 * 0.0 + 0.20 * 0.25
        assert abs(score - expected) < 0.01


# --- RubricWeights ---


class TestRubricWeights:
    def test_default_weights(self) -> None:
        w = RubricWeights()
        assert w.l1 == 0.25
        assert w.l2 == 0.25
        assert w.l3 == 0.30
        assert w.l4 == 0.20
        assert abs(w.l1 + w.l2 + w.l3 + w.l4 - 1.0) < 1e-9

    def test_custom_weights(self) -> None:
        w = RubricWeights(l1=0.10, l2=0.20, l3=0.40, l4=0.30)
        assert w.l1 == 0.10
        assert abs(w.l1 + w.l2 + w.l3 + w.l4 - 1.0) < 1e-9


# --- RunMetadata ---


class TestRunMetadata:
    def test_metadata_creation(self) -> None:
        m = RunMetadata(
            run_id="control-a-1",
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
            claude_code_version="1.0.0",
            model="claude-opus-4-6",
            started_at=datetime(2026, 2, 22, 10, 0, 0, tzinfo=UTC),
            wall_clock_minutes=25.5,
        )
        assert m.run_id == "control-a-1"
        assert m.wall_clock_minutes == 25.5
