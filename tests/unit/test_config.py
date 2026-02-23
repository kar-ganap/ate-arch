"""Tests for ate_arch.config — YAML loading and validation."""

from __future__ import annotations

import pytest

from ate_arch.config import (
    load_all_hard_constraints,
    load_all_hidden_dependencies,
    load_all_stakeholders,
    load_conflicts,
    load_partitions,
    load_scenario,
    load_stakeholder,
)
from ate_arch.models import (
    ConstraintType,
    PartitionCondition,
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


# --- Scenario ---


class TestLoadScenario:
    def test_loads_scenario_b(self) -> None:
        s = load_scenario(SCENARIO_ID)
        assert s.id == SCENARIO_ID
        assert s.name == "Multi-Region Data Platform"
        assert len(s.stakeholder_ids) == 6
        assert s.hidden_dependency_count == 4

    def test_scenario_has_correct_stakeholders(self) -> None:
        s = load_scenario(SCENARIO_ID)
        assert set(s.stakeholder_ids) == set(STAKEHOLDER_IDS)

    def test_scenario_has_correct_conflict_count(self) -> None:
        s = load_scenario(SCENARIO_ID)
        assert len(s.conflict_ids) == 8

    def test_nonexistent_scenario_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_scenario("nonexistent")


# --- Stakeholders ---


class TestLoadStakeholder:
    @pytest.mark.parametrize("stakeholder_id", STAKEHOLDER_IDS)
    def test_loads_each_stakeholder(self, stakeholder_id: str) -> None:
        s = load_stakeholder(SCENARIO_ID, stakeholder_id)
        assert s.id == stakeholder_id
        assert s.name  # non-empty
        assert s.role  # non-empty

    @pytest.mark.parametrize("stakeholder_id", STAKEHOLDER_IDS)
    def test_each_stakeholder_has_constraints(self, stakeholder_id: str) -> None:
        s = load_stakeholder(SCENARIO_ID, stakeholder_id)
        assert len(s.constraints) >= 2  # at least 2 constraints each
        hard = [c for c in s.constraints if c.type == ConstraintType.HARD]
        assert len(hard) >= 2  # at least 2 hard constraints

    def test_security_officer_has_encryption_constraint(self) -> None:
        s = load_stakeholder(SCENARIO_ID, "security_officer")
        ids = {c.id for c in s.constraints}
        assert "HC-S1-1" in ids  # AES-256 encryption

    def test_compliance_lead_has_gdpr_constraint(self) -> None:
        s = load_stakeholder(SCENARIO_ID, "compliance_lead")
        ids = {c.id for c in s.constraints}
        assert "HC-S2-1" in ids  # EU data residency

    def test_stakeholders_with_hidden_deps(self) -> None:
        """CSO, Compliance, EU Ops, and PM each have at least 1 hidden dependency."""
        for sid in ["security_officer", "compliance_lead", "regional_ops_eu", "product_manager"]:
            s = load_stakeholder(SCENARIO_ID, sid)
            assert len(s.hidden_dependencies) >= 1, f"{sid} should have hidden deps"

    def test_hidden_dep_has_trigger(self) -> None:
        s = load_stakeholder(SCENARIO_ID, "security_officer")
        for hd in s.hidden_dependencies:
            assert hd.trigger  # non-empty trigger
            assert hd.related_stakeholders  # at least one related stakeholder


class TestLoadAllStakeholders:
    def test_loads_all_six(self) -> None:
        stakeholders = load_all_stakeholders(SCENARIO_ID)
        assert len(stakeholders) == 6
        ids = {s.id for s in stakeholders}
        assert ids == set(STAKEHOLDER_IDS)


# --- Conflicts ---


class TestLoadConflicts:
    def test_loads_eight_conflicts(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        assert len(conflicts) == 8

    def test_conflict_ids_are_unique(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        ids = [c.id for c in conflicts]
        assert len(ids) == len(set(ids))

    def test_conflict_references_valid_stakeholders(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        for c in conflicts:
            assert c.stakeholder_a in STAKEHOLDER_IDS, f"{c.id}: invalid stakeholder_a"
            assert c.stakeholder_b in STAKEHOLDER_IDS, f"{c.id}: invalid stakeholder_b"

    def test_conflict_has_optimal_resolution(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        for c in conflicts:
            assert c.optimal_resolution, f"{c.id}: missing optimal resolution"

    def test_conflict_has_acceptable_resolutions(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        for c in conflicts:
            assert len(c.acceptable_resolutions) >= 1, f"{c.id}: need >= 1 acceptable"


# --- Partitions ---


class TestLoadPartitions:
    def test_loads_three_partitions(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        assert len(partitions) == 3

    def test_partition_conditions_abc(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        conditions = {p.condition for p in partitions}
        assert conditions == {PartitionCondition.A, PartitionCondition.B, PartitionCondition.C}

    def test_each_partition_has_3_per_agent(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        for p in partitions:
            assert len(p.agent_1_stakeholders) == 3, f"Condition {p.condition}"
            assert len(p.agent_2_stakeholders) == 3, f"Condition {p.condition}"

    def test_partitions_cover_all_stakeholders(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        for p in partitions:
            combined = set(p.agent_1_stakeholders) | set(p.agent_2_stakeholders)
            assert combined == set(STAKEHOLDER_IDS), f"Condition {p.condition}"

    def test_partition_a_within_cross_counts(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        pa = next(p for p in partitions if p.condition == PartitionCondition.A)
        assert len(pa.within_partition_conflicts) == 6
        assert len(pa.cross_partition_conflicts) == 2

    def test_partition_b_within_cross_counts(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        pb = next(p for p in partitions if p.condition == PartitionCondition.B)
        assert len(pb.within_partition_conflicts) == 4
        assert len(pb.cross_partition_conflicts) == 4

    def test_partition_c_within_cross_counts(self) -> None:
        partitions = load_partitions(SCENARIO_ID)
        pc = next(p for p in partitions if p.condition == PartitionCondition.C)
        assert len(pc.within_partition_conflicts) == 2
        assert len(pc.cross_partition_conflicts) == 6

    def test_partition_conflicts_cover_all_eight(self) -> None:
        conflicts = load_conflicts(SCENARIO_ID)
        conflict_ids = {c.id for c in conflicts}
        partitions = load_partitions(SCENARIO_ID)
        for p in partitions:
            combined = set(p.within_partition_conflicts) | set(p.cross_partition_conflicts)
            assert combined == conflict_ids, f"Condition {p.condition}: not all conflicts assigned"


# --- Aggregate helpers ---


class TestLoadAllHardConstraints:
    def test_count(self) -> None:
        constraints = load_all_hard_constraints(SCENARIO_ID)
        assert len(constraints) == 23

    def test_all_are_hard(self) -> None:
        constraints = load_all_hard_constraints(SCENARIO_ID)
        for c in constraints:
            assert c.type == ConstraintType.HARD

    def test_ids_unique(self) -> None:
        constraints = load_all_hard_constraints(SCENARIO_ID)
        ids = [c.id for c in constraints]
        assert len(ids) == len(set(ids))


class TestLoadAllHiddenDependencies:
    def test_count(self) -> None:
        deps = load_all_hidden_dependencies(SCENARIO_ID)
        assert len(deps) == 4

    def test_ids(self) -> None:
        deps = load_all_hidden_dependencies(SCENARIO_ID)
        ids = {d.id for d in deps}
        assert ids == {"HD1", "HD2", "HD3", "HD4"}
