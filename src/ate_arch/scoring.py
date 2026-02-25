"""4-layer rubric scoring for architecture documents."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ate_arch.models import (
    Architecture,
    Conflict,
    Constraint,
    HiddenDependency,
    PartitionCondition,
    ResolutionQuality,
    RunResult,
)
from ate_arch.simulator import LLMClient

# --- Constants ---

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 256


# --- Scoring result models ---


class ConstraintMatch(BaseModel):
    """Result of checking whether a single constraint is addressed."""

    model_config = ConfigDict(frozen=True)

    constraint_id: str
    found: bool
    evidence: str


class ConflictMatch(BaseModel):
    """Result of checking whether a single conflict is identified."""

    model_config = ConfigDict(frozen=True)

    conflict_id: str
    found: bool
    evidence: str


class ResolutionJudgment(BaseModel):
    """LLM judgment of resolution quality for one conflict."""

    model_config = ConfigDict(frozen=True)

    conflict_id: str
    quality: ResolutionQuality
    reasoning: str


class DependencyMatch(BaseModel):
    """Result of checking whether a hidden dependency is addressed."""

    model_config = ConfigDict(frozen=True)

    dependency_id: str
    found: bool
    evidence: str


class ScoringResult(BaseModel):
    """Detailed scoring breakdown for a single run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    l1_matches: list[ConstraintMatch]
    l2_matches: list[ConflictMatch]
    l3_judgments: list[ResolutionJudgment]
    l4_matches: list[DependencyMatch]

    def to_run_result(
        self,
        architecture: Architecture,
        partition_condition: PartitionCondition,
    ) -> RunResult:
        """Convert detailed results to RunResult with aggregate scores."""
        l1_found = sum(1 for m in self.l1_matches if m.found)
        l1_total = len(self.l1_matches)
        l1_score = l1_found / l1_total if l1_total else 0.0

        l2_found = sum(1 for m in self.l2_matches if m.found)
        l2_total = len(self.l2_matches)
        l2_score = l2_found / l2_total if l2_total else 0.0

        l3_dict = {j.conflict_id: j.quality for j in self.l3_judgments}

        l4_found = sum(1 for m in self.l4_matches if m.found)
        l4_total = len(self.l4_matches)
        l4_score = l4_found / l4_total if l4_total else 0.0

        return RunResult(
            run_id=self.run_id,
            architecture=architecture,
            partition_condition=partition_condition,
            l1_constraint_discovery=l1_score,
            l2_conflict_identification=l2_score,
            l3_conflict_resolution=l3_dict,
            l4_hidden_dependencies=l4_score,
        )


# --- Response parsers ---


def _parse_found_response(response: str) -> tuple[bool, str]:
    """Parse FOUND/NOT_FOUND LLM response. Returns (found, evidence)."""
    line = response.strip().split("\n")[0]
    upper = line.upper()
    if upper.startswith("FOUND:"):
        return True, line[len("FOUND:") :].strip()
    if upper.startswith("NOT_FOUND:"):
        return False, line[len("NOT_FOUND:") :].strip()
    return False, f"Unparseable response: {line}"


def _parse_quality_response(response: str) -> tuple[ResolutionQuality, str]:
    """Parse OPTIMAL/ACCEPTABLE/POOR/MISSING LLM response."""
    line = response.strip().split("\n")[0]
    upper = line.upper()
    for quality in ResolutionQuality:
        prefix = quality.value.upper() + ":"
        if upper.startswith(prefix):
            return quality, line[len(prefix) :].strip()
    return ResolutionQuality.MISSING, f"Unparseable response: {line}"


# --- Prompt templates ---


def _l1_system_prompt(constraint: Constraint, document: str) -> str:
    return f"""\
You are evaluating a software architecture document against stakeholder \
requirements.

Your task: Determine whether the following constraint is addressed in the \
architecture document.

## Constraint
- ID: {constraint.id}
- Description: {constraint.description}

## Architecture Document
{document}

## Instructions
A constraint is "addressed" if the architecture document contains a design \
decision, component, policy, or requirement that directly satisfies or \
acknowledges this constraint. Paraphrasing is acceptable — the exact wording \
does not need to match.

Respond with EXACTLY one line in this format:
FOUND: <brief evidence quote or summary>
or
NOT_FOUND: <brief explanation of what is missing>"""


def _l2_system_prompt(conflict: Conflict, document: str) -> str:
    return f"""\
You are evaluating a software architecture document for conflict awareness.

Your task: Determine whether the following conflict between stakeholders is \
identified or addressed in the architecture document.

## Conflict
- ID: {conflict.id}
- Description: {conflict.description}
- Stakeholder A ({conflict.stakeholder_a}) constraint: {conflict.constraint_a}
- Stakeholder B ({conflict.stakeholder_b}) constraint: {conflict.constraint_b}

## Architecture Document
{document}

## Instructions
A conflict is "identified" if the architecture document acknowledges the \
tension between these two requirements and either proposes a resolution or \
explicitly notes the trade-off. The conflict does not need to be labeled with \
its ID — semantic identification counts.

Respond with EXACTLY one line in this format:
FOUND: <brief evidence quote or summary>
or
NOT_FOUND: <brief explanation of what is missing>"""


def _l3_system_prompt(conflict: Conflict, document: str) -> str:
    acceptable_formatted = "\n".join(f"  - {r}" for r in conflict.acceptable_resolutions)
    return f"""\
You are a technical reviewer evaluating the quality of a conflict resolution \
in a software architecture document.

## Conflict
- ID: {conflict.id}
- Description: {conflict.description}
- Stakeholder A ({conflict.stakeholder_a}): {conflict.constraint_a}
- Stakeholder B ({conflict.stakeholder_b}): {conflict.constraint_b}

## Reference Resolutions
OPTIMAL: {conflict.optimal_resolution}
ACCEPTABLE:
{acceptable_formatted}

## Architecture Document
{document}

## Scoring Criteria
- OPTIMAL: Resolution satisfies both stakeholders' hard constraints with \
minimal compromise on preferences. Closely matches or is equivalent to the \
optimal reference resolution.
- ACCEPTABLE: Resolution satisfies hard constraints but with significant \
preference trade-offs. Matches or is similar to one of the acceptable \
reference resolutions.
- POOR: Resolution violates one or more hard constraints, or is a naive \
compromise that doesn't adequately address the tension.
- MISSING: The conflict is not addressed in the architecture document at all.

Respond with EXACTLY one line in this format:
OPTIMAL: <brief reasoning>
or
ACCEPTABLE: <brief reasoning>
or
POOR: <brief reasoning>
or
MISSING: <brief reasoning>"""


def _l4_system_prompt(dependency: HiddenDependency, document: str) -> str:
    stakeholders = ", ".join(dependency.related_stakeholders)
    return f"""\
You are evaluating a software architecture document for hidden dependency \
awareness.

Your task: Determine whether the following non-obvious dependency is \
addressed in the architecture document.

## Hidden Dependency
- ID: {dependency.id}
- Description: {dependency.description}
- Related stakeholders: {stakeholders}

## Architecture Document
{document}

## Instructions
A hidden dependency is "discovered" if the architecture document addresses \
the underlying concern described above, even if it doesn't name it as a \
"hidden dependency." Look for design decisions, constraints, or analysis \
that demonstrates awareness of this cross-cutting concern.

Respond with EXACTLY one line in this format:
FOUND: <brief evidence quote or summary>
or
NOT_FOUND: <brief explanation of what is missing>"""


# --- Scoring functions ---


def score_l1(
    document: str,
    constraints: list[Constraint],
    llm_client: LLMClient,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> list[ConstraintMatch]:
    """Check which hard constraints are addressed in the architecture document."""
    matches: list[ConstraintMatch] = []
    for constraint in constraints:
        system = _l1_system_prompt(constraint, document)
        response = llm_client.create_message(
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": "Score this constraint."}],
        )
        found, evidence = _parse_found_response(response)
        matches.append(ConstraintMatch(constraint_id=constraint.id, found=found, evidence=evidence))
    return matches


def score_l2(
    document: str,
    conflicts: list[Conflict],
    llm_client: LLMClient,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> list[ConflictMatch]:
    """Check which conflicts are identified in the architecture document."""
    matches: list[ConflictMatch] = []
    for conflict in conflicts:
        system = _l2_system_prompt(conflict, document)
        response = llm_client.create_message(
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": "Score this conflict."}],
        )
        found, evidence = _parse_found_response(response)
        matches.append(ConflictMatch(conflict_id=conflict.id, found=found, evidence=evidence))
    return matches


def score_l3(
    document: str,
    conflicts: list[Conflict],
    llm_client: LLMClient,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> list[ResolutionJudgment]:
    """Judge resolution quality for each conflict using LLM-as-judge."""
    judgments: list[ResolutionJudgment] = []
    for conflict in conflicts:
        system = _l3_system_prompt(conflict, document)
        response = llm_client.create_message(
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": "Judge this resolution."}],
        )
        quality, reasoning = _parse_quality_response(response)
        judgments.append(
            ResolutionJudgment(
                conflict_id=conflict.id,
                quality=quality,
                reasoning=reasoning,
            )
        )
    return judgments


def score_l4(
    document: str,
    dependencies: list[HiddenDependency],
    llm_client: LLMClient,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> list[DependencyMatch]:
    """Check which hidden dependencies are addressed in the document."""
    matches: list[DependencyMatch] = []
    for dep in dependencies:
        system = _l4_system_prompt(dep, document)
        response = llm_client.create_message(
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": "Score this dependency."}],
        )
        found, evidence = _parse_found_response(response)
        matches.append(DependencyMatch(dependency_id=dep.id, found=found, evidence=evidence))
    return matches


# --- Orchestrator ---


def score_run(
    run_id: str,
    document: str,
    constraints: list[Constraint],
    conflicts: list[Conflict],
    dependencies: list[HiddenDependency],
    llm_client: LLMClient,
    *,
    architecture: Architecture,
    partition_condition: PartitionCondition,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> ScoringResult:
    """Score a complete run across all 4 rubric layers."""
    l1 = score_l1(document, constraints, llm_client, model=model, temperature=temperature)
    l2 = score_l2(document, conflicts, llm_client, model=model, temperature=temperature)
    l3 = score_l3(document, conflicts, llm_client, model=model, temperature=temperature)
    l4 = score_l4(document, dependencies, llm_client, model=model, temperature=temperature)
    return ScoringResult(
        run_id=run_id,
        l1_matches=l1,
        l2_matches=l2,
        l3_judgments=l3,
        l4_matches=l4,
    )


# --- Model slug ---


def model_slug(model: str) -> str:
    """Short slug for file naming. E.g., 'claude-haiku-4-5-20251001' -> 'haiku'."""
    for keyword in ("haiku", "sonnet", "opus"):
        if keyword in model:
            return keyword
    return model.split("-")[1] if "-" in model else model


# --- Persistence ---


def _score_filename(run_id: str, scoring_model: str | None, suffix: str = "") -> str:
    """Build score filename with optional model slug."""
    slug = f"_{model_slug(scoring_model)}" if scoring_model else ""
    return f"{run_id}{slug}{suffix}.json"


def save_result(
    result: RunResult,
    scores_dir: Path,
    *,
    scoring_model: str | None = None,
) -> Path:
    """Save RunResult to scores_dir/{run_id}[_{model}].json."""
    scores_dir.mkdir(parents=True, exist_ok=True)
    path = scores_dir / _score_filename(result.run_id, scoring_model)
    path.write_text(result.model_dump_json(indent=2))
    return path


def load_result(
    run_id: str,
    scores_dir: Path,
    *,
    scoring_model: str | None = None,
) -> RunResult:
    """Load RunResult from scores_dir/{run_id}[_{model}].json."""
    path = scores_dir / _score_filename(run_id, scoring_model)
    if not path.exists():
        msg = f"Score file not found: {path}"
        raise FileNotFoundError(msg)
    return RunResult.model_validate_json(path.read_text())


def save_scoring_detail(
    detail: ScoringResult,
    scores_dir: Path,
    *,
    scoring_model: str | None = None,
) -> Path:
    """Save detailed ScoringResult to scores_dir/{run_id}[_{model}]_detail.json."""
    scores_dir.mkdir(parents=True, exist_ok=True)
    path = scores_dir / _score_filename(detail.run_id, scoring_model, "_detail")
    path.write_text(detail.model_dump_json(indent=2))
    return path
