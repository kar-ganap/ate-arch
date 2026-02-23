# Execution Guide

Step-by-step operator guide for running ate-arch experimental sessions.

## Prerequisites

- Python 3.11+ with uv
- `ANTHROPIC_API_KEY` set (for stakeholder simulation via LLM)
- Claude Code installed (`claude` CLI available)
- Project dependencies installed: `uv sync`

## 1. Scaffold Runs

Scaffold all 30 runs at once:

```bash
ate-arch batch-scaffold
```

Or scaffold a subset:

```bash
ate-arch batch-scaffold --architecture control --partition A
```

Verify scaffolding:

```bash
ate-arch verify-run control-A-1 --mode structural
```

## 2. Pre-Run Setup

### For Control Runs (Hub-and-Spoke)

```bash
# Ensure agent teams is NOT set
unset CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS

# Verify
ate-arch preflight --architecture control
```

### For Treatment Runs (Symmetric Peers)

```bash
# Enable agent teams
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# Verify
ate-arch preflight --architecture treatment
```

## 3. Run a Session

1. **Open the session guide** for reference:
   ```bash
   cat data/runs/<run_id>/session_guide.md
   ```

2. **Record the start time** and Claude Code version:
   ```bash
   claude --version
   ```

3. **Start Claude Code** in a fresh session:
   ```bash
   claude
   ```

4. **Paste the opening prompt** from the session guide.

5. **Monitor the session**:
   - Let the agent work autonomously
   - Press Escape if stuck for > 5 minutes
   - Note any anomalies in `data/runs/<run_id>/notes.md`
   - Time limit: 30 minutes (soft cap)

6. **Collect the architecture document**:
   ```bash
   cp architecture.md data/runs/<run_id>/architecture.md
   ```

7. **Save the transcript**:
   - Claude Code JSONL transcript is at:
     `~/.claude/projects/-Users-...-ate-arch/`
   - Copy the relevant JSONL file to `data/transcripts/<run_id>.jsonl`

## 4. Post-Run

Update metadata with timing and model info:

```bash
ate-arch update-metadata <run_id> \
  --wall-clock <minutes> \
  --model claude-opus-4-6 \
  --claude-version "$(claude --version)" \
  --interview-count <count> \
  --notes "any observations"
```

Verify completeness:

```bash
ate-arch verify-run <run_id> --mode complete
```

## 5. Score

Score the architecture document:

```bash
ate-arch score <run_id>
```

Use a specific model for scoring:

```bash
ate-arch score <run_id> --model claude-haiku-4-5-20251001
```

Results are saved to `data/scores/`.

## 6. Communication Analysis

For treatment runs, analyze inter-agent communication:

```bash
ate-arch analyze-comms <run_id> data/transcripts/<run_id>.jsonl
```

## Run Order

Recommended pilot order:

| # | Run ID | Architecture | Partition |
|---|--------|-------------|-----------|
| 1 | control-A-1 | control | A (75% within) |
| 2 | treatment-A-1 | treatment | A (75% within) |
| 3 | control-C-1 | control | C (25% within) |

Full execution: randomize the remaining 27 runs to avoid ordering effects.

## Troubleshooting

- **"ANTHROPIC_API_KEY not set"**: Export the key before running
- **Agent stuck**: Press Escape, note the issue, restart the run
- **Scoring errors**: Check that `architecture.md` exists and is non-empty
- **Zero communication**: Expected for control runs; concerning for treatment runs
