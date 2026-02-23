# Phase 5 Retro: Pilot

## What Worked

- Full pipeline validated end-to-end: scaffold → interview → score → comms
  analysis. All 4 pilot runs completed without manual intervention.
- Stakeholder simulator produced coherent, in-character responses across 76
  total interviews. Hidden dependencies surfaced naturally when probed.
- Scoring produced differentiated results. L3 ranged from 0.75 to 1.00, L4
  from 0.25 to 1.00. Composite scores span 0.78–1.00 across 4 runs.
- Batch scaffolding and verification caught real issues during setup (missing
  files, incomplete metadata). Two-stage verification (structural + complete)
  proved useful.
- TDD discipline held: 253 tests, all passing, zero real LLM calls in tests.

## Surprises

- **comms.py had a structural bug**: `extract_peer_messages()` scanned for
  root-level `type: "tool_use"` entries, but Claude Code JSONL transcripts nest
  tool calls inside `message.content[]` arrays. This masked all SendMessage
  data, producing false zeroes. Fixed in-phase after discovering it during
  treatment-C-1 analysis.
- **Treatment prompt was designed wrong**: Original `_treatment_prompt()` was
  written from one peer's perspective showing only 3 of 6 stakeholders. It
  needed to be from the lead agent's vantage point (same as control) but
  spawning peer agents with lateral communication permission. Root cause: Phase
  3 plan never specified treatment prompt structure; incorrect assumption about
  Agent Teams per-peer prompts. Caught by user during treatment-A-1 setup.
- **Zero peer-to-peer communication** (again): All SendMessage calls in
  treatment runs are coordinator → agent. No agent-1 ↔ agent-2 messages in
  either treatment. This is consistent across all 3 ate experiments now.
- **treatment-C-1 scored a perfect 1.00**: All 8 conflicts optimal, all 4
  hidden dependencies found. First perfect score. But treatment-A-1 scored the
  lowest (0.78). High variance in treatment runs suggests single-run results
  are unreliable.
- **Indirect collaboration through shared files**: treatment-C-1's actual
  coordination was agent-2 writing architecture.md, agent-1 reading and editing
  it, agent-2 verifying — all mediated by the coordinator via SendMessage
  instructions. Real collaboration, but not the peer-to-peer pattern Agent
  Teams is designed for.

## Deviations from Plan

- Plan called for 3 pilot runs; we ran 4 (added treatment-C-1 for the full
  2×2 matrix of architecture × partition extremes).
- Plan estimated ~46 new tests; actual is 47 (23 batch + 18 comms + 6 CLI).
  253 total vs estimated 252.
- Added python-dotenv dependency (not in plan) for API key isolation from
  .zshrc defaults.
- comms.py bug fix added `_iter_tool_uses()` helper and restructured tests to
  use nested JSONL format while preserving flat format backward compatibility.

## Pilot Results

| Run | Arch | Part | L1 | L2 | L3 | L4 | Comp | Time | Interviews | SendMsg |
|-----|------|------|----|----|----|-----|------|------|------------|---------|
| control-A-1 | hub | A | 1.00 | 1.00 | 0.75 | 1.00 | 0.93 | 9.3m | 9 (5/6) | N/A |
| treatment-A-1 | peer | A | 1.00 | 1.00 | 0.75 | 0.25 | 0.78 | 21.4m | 31 (6/6) | 5 (coord→agent) |
| control-C-1 | hub | C | 1.00 | 1.00 | 0.75 | 0.75 | 0.88 | 12.3m | 16 (6/6) | N/A |
| treatment-C-1 | peer | C | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 16.2m | 20 (6/6) | 6 (coord→agent) |

### Observations

1. **L1/L2 ceiling**: All 4 runs hit 1.00. These layers don't differentiate.
   Consider raising the bar (more constraints, subtler conflicts) or accepting
   that L3/L4 carry the signal.
2. **L3 consistency**: 0.75 in 3 of 4 runs (2 optimal + 6 acceptable). Only
   treatment-C-1 broke through with all 8 optimal. Need n>1 to assess whether
   this is stable or stochastic.
3. **L4 variance**: The most informative layer. Ranges from 0.25 to 1.00.
   Hidden dependencies require deeper probing that varies by run.
4. **Treatment overhead**: Treatment runs take ~2x longer than control (18.8
   min avg vs 10.8 min avg) and conduct more interviews (25.5 avg vs 12.5
   avg). Agent Teams adds coordination overhead regardless of outcome quality.
5. **Communication pattern**: Agent Teams enables SendMessage but agents don't
   use it peer-to-peer. Coordination happens through the lead agent reading
   subagent reports and dispatching instructions — functionally identical to
   hub-and-spoke.

## Bugs Found and Fixed

| Bug | Impact | Root Cause | Fix |
|-----|--------|-----------|-----|
| `get_opening_prompt()` hardcoded `run_num=0` | Session guides referenced wrong run IDs | Missing parameter passthrough | Added `run_num` parameter |
| Treatment prompt from peer's perspective | Would have shown only 3/6 stakeholders | Phase 3 plan gap; wrong assumption about Agent Teams | Rewrote to lead-agent vantage |
| `PartitionCondition` comments wrong | Misleading developer context | Copy-paste from initial draft | Fixed comments to match ratios |
| `comms.py` scanned wrong nesting level | All SendMessage data invisible (false zeroes) | JSONL transcript format not investigated before coding | Added `_iter_tool_uses()` for nested + flat |

## Implicit Assumptions Made Explicit

- Claude Code JSONL transcripts use nested format: tool calls are in
  `entry.message.content[].{type: "tool_use", name, input}`, not at root.
- Agent Teams `SendMessage` is the only explicit inter-agent communication
  primitive. Agents can also coordinate through shared file I/O (Read/Edit on
  the same file), which our comms analysis does not currently track.
- Haiku scoring is sufficient for L1/L2/L4 (binary found/not-found). L3
  judgments (optimal/acceptable/poor) showed reasonable discrimination but
  should be spot-checked against human judgment before the full 30-run matrix.
- Single runs are insufficient for reliable comparison. n=5 per cell (as
  designed) is the minimum for the full experiment.

## Scope Changes for Next Phase

- Phase 6 (Execution) should consider tracking indirect collaboration
  (Read/Edit on shared files) as a secondary metric alongside SendMessage.
- The 2×2 pilot matrix (A/C × control/treatment) covers extremes. Phase 6
  needs partition B runs to complete the gradient.
- comms.py now handles both nested and flat JSONL formats. Tests use both.
  The flat format can be retired once all transcripts are confirmed nested.

## Metrics

- Tests added: 47 (253 total)
- Files created: 5 (batch.py, comms.py, test_batch.py, test_comms.py,
  execution-guide.md)
- Files modified: 6 (cli.py, test_cli.py, harness.py, models.py, .gitignore,
  pyproject.toml)
- Dependencies added: 1 (python-dotenv)
- Pilot runs completed: 4
- Bugs found and fixed: 4
