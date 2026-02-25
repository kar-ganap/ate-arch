"""Generate publication-quality figures for ate-arch findings."""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ate_arch.models import ResolutionQuality, RubricWeights, RunResult

DATA = Path(__file__).parent.parent / "data"
FIGS = Path(__file__).parent.parent / "docs" / "figures"
WEIGHTS = RubricWeights()

CELL_ORDER = ["control-A", "control-C", "treatment-A", "treatment-C"]
CELL_LABELS = ["Control-A\n(hub, 25% cross)", "Control-C\n(hub, 75% cross)",
               "Treatment-A\n(peer, 25% cross)", "Treatment-C\n(peer, 75% cross)"]
CELL_COLORS = ["#90caf9", "#42a5f5", "#ffcc80", "#ff9800"]

RUNS_PER_CELL = 8


def load_sonnet_scores() -> dict[str, list[dict]]:
    """Load all Sonnet scores grouped by cell."""
    cells: dict[str, list[dict]] = {c: [] for c in CELL_ORDER}
    for cell in CELL_ORDER:
        for i in range(1, RUNS_PER_CELL + 1):
            rid = f"{cell}-{i}"
            path = DATA / "scores" / f"{rid}_sonnet.json"
            result = RunResult(**json.loads(path.read_text()))
            quals = list(result.l3_conflict_resolution.values())
            cells[cell].append({
                "run_id": rid,
                "composite": result.composite_score(WEIGHTS),
                "l1": result.l1_constraint_discovery,
                "l2": result.l2_conflict_identification,
                "l3": result.l3_score(),
                "l4": result.l4_hidden_dependencies,
                "l3_opt": sum(1 for q in quals if q == ResolutionQuality.OPTIMAL),
                "l3_acc": sum(1 for q in quals if q == ResolutionQuality.ACCEPTABLE),
                "l3_poor": sum(1 for q in quals if q == ResolutionQuality.POOR),
                "l3_miss": sum(1 for q in quals if q == ResolutionQuality.MISSING),
            })
    return cells


# Blind review scores (from findings.md Section 4.2)
BLIND_SCORES: dict[str, list[int]] = {
    "control-A": [22, 22, 20, 20, 23, 24, 22, 22],
    "control-C": [23, 24, 22, 24, 22, 21, 22, 23],
    "treatment-A": [25, 25, 25, 19, 24, 25, 25, 22],
    "treatment-C": [22, 22, 25, 27, 24, 25, 21, 27],
}


def fig1_composite_box(cells: dict[str, list[dict]]) -> None:
    """Box plot of composite scores by cell."""
    fig, ax = plt.subplots(figsize=(8, 5))

    data = [[d["composite"] for d in cells[c]] for c in CELL_ORDER]

    bp = ax.boxplot(data, patch_artist=True, widths=0.6, showmeans=True,
                    meanprops=dict(marker="D", markerfacecolor="black", markersize=5))

    for patch, color in zip(bp["boxes"], CELL_COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    # Overlay individual points
    for i, (cell, color) in enumerate(zip(CELL_ORDER, CELL_COLORS)):
        vals = [d["composite"] for d in cells[cell]]
        x = np.random.normal(i + 1, 0.04, size=len(vals))
        ax.scatter(x, vals, alpha=0.6, s=30, color="black", zorder=3)

    ax.set_xticklabels(CELL_LABELS, fontsize=9)
    ax.set_ylabel("Composite Score", fontsize=11)
    ax.set_title("Composite Scores by Cell (Sonnet 4.6 scoring, n=8)", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.3)

    # Add significance bracket for architecture main effect
    ax.annotate("", xy=(1.5, 0.98), xytext=(3.5, 0.98),
                arrowprops=dict(arrowstyle="-", color="black", lw=1.5))
    ax.text(2.5, 0.99, "p = 0.014 *", ha="center", fontsize=9, fontstyle="italic")

    plt.tight_layout()
    fig.savefig(FIGS / "composite_boxplot.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved composite_boxplot.png")


def fig2_l3_breakdown(cells: dict[str, list[dict]]) -> None:
    """Stacked bar chart of L3 resolution quality breakdown."""
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ["l3_opt", "l3_acc", "l3_poor", "l3_miss"]
    cat_labels = ["Optimal", "Acceptable", "Poor", "Missing"]
    cat_colors = ["#2e7d32", "#66bb6a", "#ef5350", "#bdbdbd"]

    x = np.arange(len(CELL_ORDER))
    width = 0.6

    # Compute means across runs for each cell
    bottoms = np.zeros(len(CELL_ORDER))
    for cat, label, color in zip(categories, cat_labels, cat_colors):
        means = [np.mean([d[cat] for d in cells[c]]) for c in CELL_ORDER]
        ax.bar(x, means, width, bottom=bottoms, label=label, color=color, alpha=0.85)
        bottoms += means

    ax.set_xticks(x)
    ax.set_xticklabels(CELL_LABELS, fontsize=9)
    ax.set_ylabel("Mean count (out of 8 conflicts)", fontsize=11)
    ax.set_title("L3 Resolution Quality Breakdown by Cell", fontsize=12)
    ax.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    fig.savefig(FIGS / "l3_breakdown.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved l3_breakdown.png")


def fig3_dose_response(cells: dict[str, list[dict]]) -> None:
    """Dose-response: treatment effect vs cross-partition %."""
    fig, ax = plt.subplots(figsize=(6, 5))

    metrics = ["composite", "l3"]
    labels = ["Composite", "L3 Resolution"]
    colors = ["#1565c0", "#e65100"]
    markers = ["o", "s"]

    cross_pcts = [25, 75]

    for metric, label, color, marker in zip(metrics, labels, colors, markers):
        ctrl_a = np.mean([d[metric] for d in cells["control-A"]])
        ctrl_c = np.mean([d[metric] for d in cells["control-C"]])
        treat_a = np.mean([d[metric] for d in cells["treatment-A"]])
        treat_c = np.mean([d[metric] for d in cells["treatment-C"]])

        effects = [treat_a - ctrl_a, treat_c - ctrl_c]
        ax.plot(cross_pcts, effects, f"-{marker}", color=color, label=label,
                markersize=8, linewidth=2)

        # Annotate values
        for pct, eff in zip(cross_pcts, effects):
            ax.annotate(f"{eff:+.2f}", (pct, eff), textcoords="offset points",
                        xytext=(10, 5), fontsize=9, color=color)

    ax.set_xlabel("Cross-partition conflicts (%)", fontsize=11)
    ax.set_ylabel("Treatment effect (Treatment - Control)", fontsize=11)
    ax.set_title("Dose-Response: Treatment Benefit vs Information Asymmetry", fontsize=12)
    ax.set_xticks(cross_pcts)
    ax.set_xticklabels(["Partition A\n(25% cross)", "Partition C\n(75% cross)"])
    ax.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
    ax.legend(fontsize=10)
    ax.set_ylim(-0.05, 0.45)

    plt.tight_layout()
    fig.savefig(FIGS / "dose_response.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved dose_response.png")


def fig4_blind_vs_rubric(cells: dict[str, list[dict]]) -> None:
    """Scatter plot: blind review score vs rubric composite score."""
    fig, ax = plt.subplots(figsize=(7, 6))

    for cell, color, label in zip(CELL_ORDER, CELL_COLORS,
                                  ["Control-A", "Control-C", "Treatment-A", "Treatment-C"]):
        composites = [d["composite"] for d in cells[cell]]
        blinds = BLIND_SCORES[cell]
        ax.scatter(composites, blinds, c=color, label=label, s=60, alpha=0.8,
                   edgecolors="black", linewidths=0.5, zorder=3)

    ax.set_xlabel("Rubric Composite Score (Sonnet 4.6)", fontsize=11)
    ax.set_ylabel("Blind Architectural Review Score (/30)", fontsize=11)
    ax.set_title("Blind Review vs Rubric Scoring (32 runs)", fontsize=12)
    ax.legend(fontsize=9, loc="lower right")

    # Reference line
    x_range = np.linspace(0.2, 1.05, 100)
    ax.plot(x_range, 18 + 12 * x_range, ":", color="gray", alpha=0.4, label="_nolegend_")

    ax.set_xlim(0.2, 1.05)
    ax.set_ylim(17, 29)

    plt.tight_layout()
    fig.savefig(FIGS / "blind_vs_rubric.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved blind_vs_rubric.png")


def main() -> None:
    print("Loading scores...")
    cells = load_sonnet_scores()

    print("Generating figures:")
    np.random.seed(42)
    fig1_composite_box(cells)
    fig2_l3_breakdown(cells)
    fig3_dose_response(cells)
    fig4_blind_vs_rubric(cells)

    print(f"\nAll figures saved to {FIGS}/")


if __name__ == "__main__":
    main()
