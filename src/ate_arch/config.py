"""Configuration loading from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from ate_arch.models import (
    Conflict,
    Constraint,
    ConstraintType,
    HiddenDependency,
    Partition,
    Scenario,
    Stakeholder,
)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def load_yaml(path: Path) -> dict[str, object]:
    """Load a YAML file and return its contents as a dict."""
    with open(path) as f:
        result = yaml.safe_load(f)
    if not isinstance(result, dict):
        msg = f"Expected dict at top level of {path}, got {type(result).__name__}"
        raise TypeError(msg)
    return result


def load_scenario(scenario_id: str) -> Scenario:
    """Load a scenario definition from config/scenarios/<id>.yaml."""
    path = CONFIG_DIR / "scenarios" / f"{scenario_id}.yaml"
    data = load_yaml(path)
    return Scenario.model_validate(data)


def load_stakeholder(scenario_id: str, stakeholder_id: str) -> Stakeholder:
    """Load a stakeholder constraint sheet from config/stakeholders/<scenario>/<id>.yaml."""
    path = CONFIG_DIR / "stakeholders" / scenario_id / f"{stakeholder_id}.yaml"
    data = load_yaml(path)
    return Stakeholder.model_validate(data)


def load_all_stakeholders(scenario_id: str) -> list[Stakeholder]:
    """Load all stakeholder constraint sheets for a scenario."""
    scenario = load_scenario(scenario_id)
    return [load_stakeholder(scenario_id, sid) for sid in scenario.stakeholder_ids]


def load_all_hard_constraints(scenario_id: str) -> list[Constraint]:
    """Load all hard constraints across all stakeholders for a scenario."""
    stakeholders = load_all_stakeholders(scenario_id)
    constraints: list[Constraint] = []
    for s in stakeholders:
        constraints.extend(c for c in s.constraints if c.type == ConstraintType.HARD)
    return constraints


def load_all_hidden_dependencies(scenario_id: str) -> list[HiddenDependency]:
    """Load all hidden dependencies across all stakeholders for a scenario."""
    stakeholders = load_all_stakeholders(scenario_id)
    deps: list[HiddenDependency] = []
    for s in stakeholders:
        deps.extend(s.hidden_dependencies)
    return deps


def load_conflicts(scenario_id: str) -> list[Conflict]:
    """Load all conflicts for a scenario from config/conflicts.yaml."""
    path = CONFIG_DIR / "conflicts.yaml"
    data = load_yaml(path)
    if data.get("scenario") != scenario_id:
        msg = f"Conflicts file is for scenario '{data.get('scenario')}', expected '{scenario_id}'"
        raise ValueError(msg)
    raw_conflicts = data.get("conflicts")
    if not isinstance(raw_conflicts, list):
        msg = f"Expected 'conflicts' to be a list in {path}"
        raise TypeError(msg)
    return [Conflict.model_validate(c) for c in raw_conflicts]


def load_partitions(scenario_id: str) -> list[Partition]:
    """Load all partition configurations for a scenario from config/partitions.yaml."""
    path = CONFIG_DIR / "partitions.yaml"
    data = load_yaml(path)
    if data.get("scenario") != scenario_id:
        msg = f"Partitions file is for scenario '{data.get('scenario')}', expected '{scenario_id}'"
        raise ValueError(msg)
    raw_partitions = data.get("partitions")
    if not isinstance(raw_partitions, list):
        msg = f"Expected 'partitions' to be a list in {path}"
        raise TypeError(msg)
    return [Partition.model_validate(p) for p in raw_partitions]
