# Agent Teams Eval — Architecture Design (ate-arch)

Experimental comparison of Claude Code with Agent Teams (symmetric peers) vs
default Claude Code (hub-and-spoke subagents) for software architecture design
with simulated stakeholder requirements gathering.

**Key finding:** Agent Teams produce significantly better architecture documents
when stakeholder information is distributed across agents. The effect is large
(Cohen's d = +0.99 composite, +1.04 L3 resolution quality) and statistically
significant (p < 0.05, Mann-Whitney U). The advantage concentrates in the
high-information-asymmetry condition where 75% of conflicts require cross-agent
information sharing.

This is the **first statistically significant result** across three ate-series
experiments. Prior experiments
([ate](https://github.com/kar-ganap/ate),
[ate-features](https://github.com/kar-ganap/ate-features))
found ceiling effects and zero communication on easier tasks.

Part of the [ate-series](https://github.com/kar-ganap/ate-series).

## Results at a Glance

| Cell | n | Composite | L3 Resolution | L4 Hidden Deps |
|------|---|-----------|---------------|----------------|
| Control-A (hub, 25% cross) | 8 | 0.81 | 0.63 | 0.44 |
| Control-C (hub, 75% cross) | 8 | 0.84 | 0.68 | 0.50 |
| Treatment-A (peer, 25% cross) | 8 | 0.88 | 0.76 | 0.63 |
| Treatment-C (peer, 75% cross) | 8 | 0.91 | 0.83 | 0.69 |

See [findings](docs/findings.md) for full analysis including statistical tests,
blind architectural review, and dose-response curves.

## Design

- **Domain:** Multi-region data platform with 6 simulated stakeholders (LLM-backed)
- **Architecture conditions:** Hub-and-spoke (control) vs symmetric peers (treatment)
- **Partition conditions:** A (25% cross-partition conflicts) vs C (75% cross)
- **Rubric:** 4-layer — constraint discovery (L1), conflict identification (L2),
  resolution quality (L3, LLM-as-judge), hidden dependencies (L4)
- **Runs:** 2 architectures x 2 partitions x 8 runs = 32 total

See [experiment-design.md](docs/experiment-design.md) for the full protocol and
[architecture.md](docs/architecture.md) for system diagrams.

## Quick Start

```bash
uv sync --group dev --group scoring
uv run ate-arch list-runs
uv run ate-arch score <run-id>
```

## Validation Gates

```bash
make test       # 330 unit tests
make lint       # ruff linter
make typecheck  # mypy strict
```
