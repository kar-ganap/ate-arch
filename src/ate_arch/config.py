"""Configuration loading from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from ate_arch.models import Scenario, Stakeholder

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
