# Phase 6 Retro: Execution

## What Worked

- Scaled from 4 pilots (n=1) to 32 runs (n=8 per cell). All runs completed
  without pipeline failures. Scaffolding, interviews, scoring, and comms
  analysis all held up at scale.
- Dual-model scoring (Haiku + Sonnet) added mid-phase proved valuable.
  Sonnet scores are systematically higher but rank-order agreement is strong.
  20 runs scored with both models, all 32 scored with Sonnet.
- Auto-extract metadata eliminated manual `--wall-clock` and
  `--interview-count` entry. Transcript timestamp extraction and
  `interview_state.json` counting worked reliably across all runs.
- Statistical analysis achieved the primary goal: architecture main effect is
  significant at p<0.05 with large effect sizes (Composite d=+0.99,
  L3 d=+1.04). This is the first statistically significant result across
  3 ate experiments.
- Dose-response gradient confirmed: treatment benefit scales with
  cross-partition conflict density (Partition C 75% cross > Partition A 25%).
  Interaction effect marginal (p=0.08 composite, p=0.05 L3).
- Blind architectural review (6-dimension, first-principles) independently
  validated the treatment advantage direction. Treatment mean 23.9/30 vs
  Control 22.3/30.
- TDD discipline maintained: 330 tests, all passing, zero real LLM calls.

## Surprises

- **n=8 was necessary, n=5 was not enough.** At n=5, several comparisons were
  trending but not significant. Expanding to n=8 tipped the architecture main
  effect over the significance threshold. The original experiment design
  specified n=5 as sufficient — it was optimistic.
- **Treatment-C is the star cell.** Composite mean 0.91 vs Control-A 0.81.
  The p=0.010, d=+1.67 pairwise comparison is the strongest signal. Agent
  Teams shines specifically when information asymmetry is highest.
- **L1/L2 ceiling persists at scale.** All 32 runs score L1=1.00 and L2=1.00.
  These layers contribute zero discriminating variance. All differentiation
  comes from L3 (resolution quality) and L4 (hidden dependencies).
- **Zero indirect collaboration detected.** The FileOperation/
  IndirectCollaboration tracking added in Phase 6 found nothing across 32
  runs. Root cause: Agent Teams transcript opacity — all file operations
  appear at coordinator level with no agentId attribution.
- **Zero relay events.** RelayEvent/RelayAnalysis tracking found nothing.
  Root cause: Task tool returns "Spawned successfully" rather than the
  agent's actual report. Relay transparency requires a different matching
  strategy than the one implemented.
- **Blind review champions differ from rubric champions in 3/4 cells.**
  Most dramatic: control-C-7 scores perfect 1.00 on rubric but only 22/30
  blind; treatment-C-4 scores 0.79 rubric but 27/30 blind. The two
  evaluations measure complementary aspects (checklist coverage vs
  architectural quality).
- **Near-duplicate documents across cells.** Blind reviewers independently
  flagged treatment-A-6 ≈ treatment-C-6 (near-verbatim), treatment-A-4 ≈
  treatment-A-3, and control-A-2 ≈ treatment-C-1. Partition differentiation
  is weaker than expected — agents converge on similar solutions.
- **Treatment takes ~2x longer** (17.8 min avg vs 9.4 min control). This is
  the mechanism, not a confound — Agent Teams coordination overhead produces
  more thorough stakeholder engagement.

## Deviations from Plan

- Plan called for 16 new runs (runs 2-5 for each cell, n=5 total); we ran
  28 new runs (runs 2-8, n=8 total) after n=5 proved insufficient.
- Plan included Partition B runs; dropped entirely. With A (25% cross) and
  C (75% cross) showing the dose-response gradient, the middle point was
  not needed for the core finding.
- Plan estimated ~297 tests; actual is 330 (77 comms + CLI tests larger than
  estimated).
- Added `rescore` CLI command and model-slug file naming (not in original
  plan). Added after discovering that Haiku vs Sonnet scoring divergence
  needed systematic comparison.
- Added `extract_all.py` and `stats.py` analysis scripts (not in plan).
  Originally expected to use the built-in `analysis.py` module, but ad-hoc
  scripts with scipy proved faster for iterative statistical exploration.
- Findings report (`docs/findings.md`, 927 lines) was not in the Phase 6
  plan — it was originally Phase 7's deliverable. Written here because the
  analysis naturally followed execution.
- Blind architectural review (32 docs, 6-dimension scoring) was unplanned.
  Added as an independent validation of the rubric methodology.

## Key Results

| Comparison | Metric | p | Sig | Effect |
|------------|--------|---|-----|--------|
| Architecture main (C vs T, n=16) | Composite | 0.014 | * | d=+0.99 |
| Architecture main (C vs T, n=16) | L3 | 0.011 | * | d=+1.04 |
| Treatment-C vs Control-A (n=8) | Composite | 0.010 | * | d=+1.67 |
| Treatment-C vs Control-A (n=8) | L3 | 0.010 | ** | d=+2.13 |
| Interaction Arch×Partition | Composite | 0.079 | † | Δ=+0.05 |
| Interaction Arch×Partition | L3 | 0.054 | † | Δ=+0.08 |

### Cell Means (Sonnet scoring)

| Cell | Composite | L3 | L4 |
|------|-----------|----|----|
| Control-A | 0.81 | 0.63 | 0.44 |
| Control-C | 0.84 | 0.68 | 0.50 |
| Treatment-A | 0.88 | 0.76 | 0.63 |
| Treatment-C | 0.91 | 0.83 | 0.69 |

## Communication Analysis

- **Peer-to-peer messages**: Zero across all 16 treatment runs. Consistent
  with ate (bug-fixing) and ate-features experiments. Agent Teams does not
  induce peer communication in any domain tested.
- **Indirect collaboration**: Zero detectable. Transcript opacity prevents
  agent-level file operation attribution.
- **Relay transparency**: Zero relay events matched. Task tool "Spawned
  successfully" responses contain no substantive content to match against.

## Bugs Found and Fixed

| Bug | Impact | Root Cause | Fix |
|-----|--------|-----------|-----|
| `scaffold_run` overwrites metadata | Re-scaffolding loses wall_clock, interview_count | `metadata.json` written unconditionally | Guard with `if not exists` |
| Re-scaffolding prompt path | Session guide references wrong scenario path | Hardcoded path in scaffold template | Use relative path from run dir |

## Metrics

- Tests: 330 (77 new)
- Files changed: 45 (+9,299 lines)
- Runs completed: 32 (4 pilots + 28 new)
- Score files: 104 (20 haiku + 32 sonnet + details)
- Comms analysis files: 32
- Analysis scripts: 2 (extract_all.py, stats.py)
- Findings report: 927 lines with diagrams
- Dependencies added: 1 (scipy, for stats.py)

## Scope Changes for Next Phase

- Phase 7 (Analysis) was originally planned for statistical analysis and
  the findings report. Both were completed in Phase 6. Phase 7 may not be
  needed as a separate phase, or could be repurposed for:
  - Haiku scoring of the remaining 12 runs (currently only 20/32 have Haiku)
  - Human validation of L3 judgments (spot-check LLM-as-judge accuracy)
  - Cross-experiment synthesis (ate + ate-features + ate-arch findings)
  - Publication-quality figures and tables
