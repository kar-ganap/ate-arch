"""Tests for ate_arch.scoring — 4-layer rubric scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ate_arch.models import (
    Architecture,
    Conflict,
    Constraint,
    ConstraintType,
    HiddenDependency,
    PartitionCondition,
    ResolutionQuality,
    RubricWeights,
)
from ate_arch.scoring import (
    ConflictMatch,
    ConstraintMatch,
    DependencyMatch,
    ResolutionJudgment,
    ScoringResult,
    load_result,
    save_result,
    save_scoring_detail,
    score_l1,
    score_l2,
    score_l3,
    score_l4,
    score_run,
)

# --- Fake LLM Client ---


class FakeLLMClient:
    """Fake LLM client for scoring tests. Returns canned responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or ["FOUND: test evidence"])
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


# --- Test fixtures ---


def _make_constraint(cid: str = "HC-S1-1", desc: str = "AES-256 encryption") -> Constraint:
    return Constraint(id=cid, description=desc, type=ConstraintType.HARD)


def _make_conflict(
    cid: str = "C1",
    desc: str = "Encryption vendor lock-in vs audit transparency",
    optimal: str = "Use open-source encryption",
    acceptable: list[str] | None = None,
) -> Conflict:
    return Conflict(
        id=cid,
        description=desc,
        stakeholder_a="security_officer",
        constraint_a="P-S1-1",
        stakeholder_b="compliance_lead",
        constraint_b="P-S2-2",
        optimal_resolution=optimal,
        acceptable_resolutions=acceptable or ["Use commercial with audit rights"],
    )


def _make_dependency(
    did: str = "HD1",
    desc: str = "Key rotation dual-key windows",
) -> HiddenDependency:
    return HiddenDependency(
        id=did,
        description=desc,
        trigger="key rotation lifecycle",
        related_stakeholders=["security_officer", "regional_ops_eu"],
    )


SAMPLE_DOCUMENT = """\
# Architecture Document

## System Overview
The platform uses AES-256 encryption for all data at rest and TLS 1.3 in transit.

## Conflict Resolution
We identified a conflict between vendor lock-in and audit transparency.
Resolution: Use open-source encryption libraries (OpenSSL/libsodium).

## Hidden Dependencies
Key rotation requires dual-key windows to avoid service disruption.
"""


# --- Response parsing (tested via L1/L2/L3/L4 functions) ---


class TestParsingViaL1:
    """Response parsing is tested indirectly through the scoring functions."""

    def test_found_prefix(self) -> None:
        llm = FakeLLMClient(["FOUND: uses AES-256 encryption"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert len(matches) == 1
        assert matches[0].found is True
        assert "AES-256" in matches[0].evidence

    def test_not_found_prefix(self) -> None:
        llm = FakeLLMClient(["NOT_FOUND: no mention of encryption"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert matches[0].found is False

    def test_case_insensitive_prefix(self) -> None:
        llm = FakeLLMClient(["found: uses encryption"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert matches[0].found is True

    def test_multiline_uses_first_line(self) -> None:
        llm = FakeLLMClient(["FOUND: evidence here\nExtra detail line"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert matches[0].found is True
        assert "Extra" not in matches[0].evidence

    def test_unparseable_defaults_not_found(self) -> None:
        llm = FakeLLMClient(["The document mentions encryption."])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert matches[0].found is False


class TestParsingViaL3:
    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ("OPTIMAL: matches reference", ResolutionQuality.OPTIMAL),
            ("ACCEPTABLE: reasonable trade-off", ResolutionQuality.ACCEPTABLE),
            ("POOR: violates constraint", ResolutionQuality.POOR),
            ("MISSING: not addressed", ResolutionQuality.MISSING),
        ],
    )
    def test_quality_prefixes(self, response: str, expected: ResolutionQuality) -> None:
        llm = FakeLLMClient([response])
        judgments = score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert judgments[0].quality == expected

    def test_quality_unparseable_defaults_missing(self) -> None:
        llm = FakeLLMClient(["The resolution seems okay."])
        judgments = score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert judgments[0].quality == ResolutionQuality.MISSING


# --- L1: Constraint Discovery ---


class TestScoreL1:
    def test_all_found(self) -> None:
        constraints = [_make_constraint(f"HC-{i}", f"Constraint {i}") for i in range(3)]
        llm = FakeLLMClient(["FOUND: evidence"])
        matches = score_l1(SAMPLE_DOCUMENT, constraints, llm)
        assert all(m.found for m in matches)
        assert len(matches) == 3

    def test_none_found(self) -> None:
        constraints = [_make_constraint(f"HC-{i}", f"Constraint {i}") for i in range(3)]
        llm = FakeLLMClient(["NOT_FOUND: missing"])
        matches = score_l1(SAMPLE_DOCUMENT, constraints, llm)
        assert not any(m.found for m in matches)

    def test_partial(self) -> None:
        constraints = [_make_constraint(f"HC-{i}", f"Constraint {i}") for i in range(4)]
        llm = FakeLLMClient(["FOUND: yes", "NOT_FOUND: no"])
        matches = score_l1(SAMPLE_DOCUMENT, constraints, llm)
        found_count = sum(1 for m in matches if m.found)
        assert found_count == 2  # alternating: found, not, found, not

    def test_returns_constraint_matches(self) -> None:
        llm = FakeLLMClient(["FOUND: evidence"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert isinstance(matches[0], ConstraintMatch)
        assert matches[0].constraint_id == "HC-S1-1"

    def test_prompt_contains_constraint(self) -> None:
        constraint = _make_constraint("HC-S1-1", "AES-256 encryption at rest")
        llm = FakeLLMClient(["FOUND: yes"])
        score_l1(SAMPLE_DOCUMENT, [constraint], llm)
        system = llm.calls[0]["system"]
        assert "HC-S1-1" in system
        assert "AES-256 encryption at rest" in system

    def test_prompt_contains_document(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        system = llm.calls[0]["system"]
        assert "Architecture Document" in system

    def test_uses_specified_model(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm, model="claude-sonnet-4-6")
        assert llm.calls[0]["model"] == "claude-sonnet-4-6"

    def test_empty_constraints(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        matches = score_l1(SAMPLE_DOCUMENT, [], llm)
        assert matches == []
        assert llm.call_count == 0

    def test_evidence_preserved(self) -> None:
        llm = FakeLLMClient(["FOUND: uses AES-256 in section 3.2"])
        matches = score_l1(SAMPLE_DOCUMENT, [_make_constraint()], llm)
        assert "AES-256" in matches[0].evidence

    def test_one_call_per_constraint(self) -> None:
        constraints = [_make_constraint(f"HC-{i}", f"C{i}") for i in range(5)]
        llm = FakeLLMClient(["FOUND: yes"])
        score_l1(SAMPLE_DOCUMENT, constraints, llm)
        assert llm.call_count == 5


# --- L2: Conflict Identification ---


class TestScoreL2:
    def test_all_found(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(3)]
        llm = FakeLLMClient(["FOUND: addressed in section 4"])
        matches = score_l2(SAMPLE_DOCUMENT, conflicts, llm)
        assert all(m.found for m in matches)

    def test_none_found(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(3)]
        llm = FakeLLMClient(["NOT_FOUND: not mentioned"])
        matches = score_l2(SAMPLE_DOCUMENT, conflicts, llm)
        assert not any(m.found for m in matches)

    def test_partial(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(4)]
        llm = FakeLLMClient(["FOUND: yes", "NOT_FOUND: no"])
        matches = score_l2(SAMPLE_DOCUMENT, conflicts, llm)
        found_count = sum(1 for m in matches if m.found)
        assert found_count == 2

    def test_returns_conflict_matches(self) -> None:
        llm = FakeLLMClient(["FOUND: identified"])
        matches = score_l2(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert isinstance(matches[0], ConflictMatch)
        assert matches[0].conflict_id == "C1"

    def test_prompt_contains_conflict_description(self) -> None:
        conflict = _make_conflict("C1", "Encryption lock-in vs transparency")
        llm = FakeLLMClient(["FOUND: yes"])
        score_l2(SAMPLE_DOCUMENT, [conflict], llm)
        system = llm.calls[0]["system"]
        assert "Encryption lock-in vs transparency" in system

    def test_prompt_contains_constraint_ids(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        score_l2(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        system = llm.calls[0]["system"]
        assert "P-S1-1" in system
        assert "P-S2-2" in system

    def test_prompt_contains_document(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        score_l2(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        system = llm.calls[0]["system"]
        assert "Architecture Document" in system

    def test_empty_conflicts(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        matches = score_l2(SAMPLE_DOCUMENT, [], llm)
        assert matches == []
        assert llm.call_count == 0


# --- L3: Conflict Resolution Quality ---


class TestScoreL3:
    def test_all_optimal(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(3)]
        llm = FakeLLMClient(["OPTIMAL: matches reference"])
        judgments = score_l3(SAMPLE_DOCUMENT, conflicts, llm)
        assert all(j.quality == ResolutionQuality.OPTIMAL for j in judgments)

    def test_all_missing(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(3)]
        llm = FakeLLMClient(["MISSING: not addressed"])
        judgments = score_l3(SAMPLE_DOCUMENT, conflicts, llm)
        assert all(j.quality == ResolutionQuality.MISSING for j in judgments)

    def test_mixed_quality(self) -> None:
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(4)]
        llm = FakeLLMClient(
            [
                "OPTIMAL: perfect",
                "ACCEPTABLE: trade-off",
                "POOR: violates constraint",
                "MISSING: not addressed",
            ]
        )
        judgments = score_l3(SAMPLE_DOCUMENT, conflicts, llm)
        qualities = [j.quality for j in judgments]
        assert qualities == [
            ResolutionQuality.OPTIMAL,
            ResolutionQuality.ACCEPTABLE,
            ResolutionQuality.POOR,
            ResolutionQuality.MISSING,
        ]

    def test_returns_resolution_judgments(self) -> None:
        llm = FakeLLMClient(["OPTIMAL: good"])
        judgments = score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert isinstance(judgments[0], ResolutionJudgment)
        assert judgments[0].conflict_id == "C1"

    def test_prompt_contains_optimal_resolution(self) -> None:
        conflict = _make_conflict(optimal="Use open-source encryption")
        llm = FakeLLMClient(["OPTIMAL: yes"])
        score_l3(SAMPLE_DOCUMENT, [conflict], llm)
        system = llm.calls[0]["system"]
        assert "open-source encryption" in system.lower()

    def test_prompt_contains_acceptable_resolutions(self) -> None:
        conflict = _make_conflict(acceptable=["Use commercial with audit rights"])
        llm = FakeLLMClient(["OPTIMAL: yes"])
        score_l3(SAMPLE_DOCUMENT, [conflict], llm)
        system = llm.calls[0]["system"]
        assert "audit rights" in system.lower()

    def test_prompt_contains_document(self) -> None:
        llm = FakeLLMClient(["OPTIMAL: yes"])
        score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        system = llm.calls[0]["system"]
        assert "Architecture Document" in system

    def test_empty_conflicts(self) -> None:
        llm = FakeLLMClient(["OPTIMAL: yes"])
        judgments = score_l3(SAMPLE_DOCUMENT, [], llm)
        assert judgments == []
        assert llm.call_count == 0

    def test_reasoning_preserved(self) -> None:
        llm = FakeLLMClient(["OPTIMAL: closely matches the reference"])
        judgments = score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert "matches the reference" in judgments[0].reasoning

    def test_uses_scoring_temperature(self) -> None:
        llm = FakeLLMClient(["OPTIMAL: yes"])
        score_l3(SAMPLE_DOCUMENT, [_make_conflict()], llm)
        assert llm.calls[0]["temperature"] == pytest.approx(0.3)


# --- L4: Hidden Dependency Discovery ---


class TestScoreL4:
    def test_all_found(self) -> None:
        deps = [_make_dependency(f"HD{i}", f"Dep {i}") for i in range(3)]
        llm = FakeLLMClient(["FOUND: addressed"])
        matches = score_l4(SAMPLE_DOCUMENT, deps, llm)
        assert all(m.found for m in matches)

    def test_none_found(self) -> None:
        deps = [_make_dependency(f"HD{i}", f"Dep {i}") for i in range(3)]
        llm = FakeLLMClient(["NOT_FOUND: missing"])
        matches = score_l4(SAMPLE_DOCUMENT, deps, llm)
        assert not any(m.found for m in matches)

    def test_partial(self) -> None:
        deps = [_make_dependency(f"HD{i}", f"Dep {i}") for i in range(4)]
        llm = FakeLLMClient(["FOUND: yes", "NOT_FOUND: no"])
        matches = score_l4(SAMPLE_DOCUMENT, deps, llm)
        found_count = sum(1 for m in matches if m.found)
        assert found_count == 2

    def test_returns_dependency_matches(self) -> None:
        llm = FakeLLMClient(["FOUND: addressed"])
        matches = score_l4(SAMPLE_DOCUMENT, [_make_dependency()], llm)
        assert isinstance(matches[0], DependencyMatch)
        assert matches[0].dependency_id == "HD1"

    def test_prompt_contains_description(self) -> None:
        dep = _make_dependency("HD1", "Key rotation dual-key windows")
        llm = FakeLLMClient(["FOUND: yes"])
        score_l4(SAMPLE_DOCUMENT, [dep], llm)
        system = llm.calls[0]["system"]
        assert "Key rotation dual-key windows" in system

    def test_prompt_contains_related_stakeholders(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        score_l4(SAMPLE_DOCUMENT, [_make_dependency()], llm)
        system = llm.calls[0]["system"]
        assert "security_officer" in system

    def test_empty_dependencies(self) -> None:
        llm = FakeLLMClient(["FOUND: yes"])
        matches = score_l4(SAMPLE_DOCUMENT, [], llm)
        assert matches == []
        assert llm.call_count == 0


# --- Orchestrator ---


class TestScoreRun:
    def test_calls_all_four_layers(self) -> None:
        constraints = [_make_constraint()]
        conflicts = [_make_conflict()]
        deps = [_make_dependency()]
        # Responses: 1 L1 + 1 L2 + 1 L3 + 1 L4 = 4 calls
        llm = FakeLLMClient(
            [
                "FOUND: constraint",
                "FOUND: conflict",
                "OPTIMAL: good",
                "FOUND: dependency",
            ]
        )
        result = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            constraints,
            conflicts,
            deps,
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        assert llm.call_count == 4
        assert len(result.l1_matches) == 1
        assert len(result.l2_matches) == 1
        assert len(result.l3_judgments) == 1
        assert len(result.l4_matches) == 1

    def test_returns_scoring_result(self) -> None:
        llm = FakeLLMClient(["FOUND: yes", "FOUND: yes", "OPTIMAL: yes", "FOUND: yes"])
        result = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        assert isinstance(result, ScoringResult)
        assert result.run_id == "control-A-1"

    def test_to_run_result(self) -> None:
        llm = FakeLLMClient(
            [
                "FOUND: yes",
                "FOUND: yes",
                "OPTIMAL: good",
                "FOUND: yes",
            ]
        )
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        run_result = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        assert run_result.run_id == "control-A-1"
        assert run_result.l1_constraint_discovery == 1.0
        assert run_result.l2_conflict_identification == 1.0
        assert run_result.l3_conflict_resolution == {"C1": ResolutionQuality.OPTIMAL}
        assert run_result.l4_hidden_dependencies == 1.0

    def test_composite_score(self) -> None:
        llm = FakeLLMClient(
            [
                "FOUND: yes",
                "FOUND: yes",
                "OPTIMAL: good",
                "FOUND: yes",
            ]
        )
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        run_result = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        # All 1.0: 0.25*1 + 0.25*1 + 0.30*1 + 0.20*1 = 1.0
        assert run_result.composite_score(RubricWeights()) == pytest.approx(1.0)

    def test_passes_model_through(self) -> None:
        llm = FakeLLMClient(["FOUND: yes", "FOUND: yes", "OPTIMAL: y", "FOUND: yes"])
        score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
            model="claude-sonnet-4-6",
        )
        for call in llm.calls:
            assert call["model"] == "claude-sonnet-4-6"

    def test_mixed_scores(self) -> None:
        constraints = [_make_constraint(f"HC-{i}", f"C{i}") for i in range(4)]
        conflicts = [_make_conflict(f"C{i}", f"Conflict {i}") for i in range(2)]
        deps = [_make_dependency(f"HD{i}", f"D{i}") for i in range(2)]
        # 4 L1 (2 found, 2 not) + 2 L2 (1 found, 1 not) + 2 L3 + 2 L4 (1 found, 1 not)
        llm = FakeLLMClient(
            [
                "FOUND: yes",
                "NOT_FOUND: no",
                "FOUND: yes",
                "NOT_FOUND: no",  # L1
                "FOUND: yes",
                "NOT_FOUND: no",  # L2
                "OPTIMAL: good",
                "POOR: bad",  # L3
                "FOUND: yes",
                "NOT_FOUND: no",  # L4
            ]
        )
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            constraints,
            conflicts,
            deps,
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        run_result = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        assert run_result.l1_constraint_discovery == pytest.approx(0.5)
        assert run_result.l2_conflict_identification == pytest.approx(0.5)
        # L3: (1.0 + 0.33) / 2 = 0.665
        assert run_result.l3_score() == pytest.approx(0.665)
        assert run_result.l4_hidden_dependencies == pytest.approx(0.5)


# --- Persistence ---


class TestPersistence:
    def test_save_result_creates_file(self, tmp_path: Path) -> None:
        llm = FakeLLMClient(["FOUND: y", "FOUND: y", "OPTIMAL: y", "FOUND: y"])
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        run_result = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        path = save_result(run_result, tmp_path)
        assert path.exists()
        assert path.name == "control-A-1.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        llm = FakeLLMClient(["FOUND: y", "FOUND: y", "OPTIMAL: y", "FOUND: y"])
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        original = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        save_result(original, tmp_path)
        loaded = load_result("control-A-1", tmp_path)
        assert loaded.run_id == original.run_id
        assert loaded.l1_constraint_discovery == original.l1_constraint_discovery
        assert loaded.l3_conflict_resolution == original.l3_conflict_resolution

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_result("nonexistent", tmp_path)

    def test_scores_dir_created(self, tmp_path: Path) -> None:
        scores_dir = tmp_path / "scores"
        llm = FakeLLMClient(["FOUND: y", "FOUND: y", "OPTIMAL: y", "FOUND: y"])
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        run_result = scoring.to_run_result(Architecture.CONTROL, PartitionCondition.A)
        path = save_result(run_result, scores_dir)
        assert path.exists()

    def test_save_scoring_detail(self, tmp_path: Path) -> None:
        llm = FakeLLMClient(["FOUND: y", "FOUND: y", "OPTIMAL: y", "FOUND: y"])
        scoring = score_run(
            "control-A-1",
            SAMPLE_DOCUMENT,
            [_make_constraint()],
            [_make_conflict()],
            [_make_dependency()],
            llm,
            architecture=Architecture.CONTROL,
            partition_condition=PartitionCondition.A,
        )
        path = save_scoring_detail(scoring, tmp_path)
        assert path.exists()
        assert path.name == "control-A-1_detail.json"
