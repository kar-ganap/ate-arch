# Phase 7 Plan: Documentation

## Context

Phase 6 complete and merged. 32 runs executed, scored, statistically analyzed.
927-line findings report written. Experiment is done — this phase wraps up with
documentation, cross-linking, and figures.

## Deliverables

### 1. README.md for ate-arch
Project overview, key finding, results table, series links, quick start.

### 2. docs/architecture.md
Full system context with 5 mermaid diagrams: experiment protocol flow, system
boundaries, module dependency graph, data flow, 2×2 experimental design with
conflict graphs.

### 3. scripts/figures.py
Matplotlib publication-quality charts: composite box plots, L3 breakdown bars,
dose-response curve, blind vs rubric scatter. Output to docs/figures/.

### 4. Figure references in docs/findings.md
Inline image references to the generated PNGs.

### 5. ate and ate-features README updates
Expand both READMEs with key findings, series links, results tables.

### 6. ate-series index repo
New `kar-ganap/ate-series` repo with cross-experiment comparison table, mermaid
timeline, and synthesis of findings across all three experiments.

### 7. CLAUDE.md update
Final project state.

## Acceptance Criteria

- `make test` passes (330 tests)
- `make lint` clean
- `make typecheck` clean
- All 4 PNGs generated in docs/figures/
- All 4 repos have consistent cross-links
- ate-series repo live on GitHub
