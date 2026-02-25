"""Statistical analysis of ate-arch experiment — Sonnet 4.6 scores."""
import json
import random
import sys
from itertools import combinations
from pathlib import Path

from scipy.stats import mannwhitneyu

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ate_arch.models import RubricWeights, RunResult

DATA = Path(__file__).parent.parent / "data"
WEIGHTS = RubricWeights()

RUNS = [
    "control-A-1", "control-A-2", "control-A-3", "control-A-4", "control-A-5",
    "control-A-6", "control-A-7", "control-A-8",
    "control-C-1", "control-C-2", "control-C-3", "control-C-4", "control-C-5",
    "control-C-6", "control-C-7", "control-C-8",
    "treatment-A-1", "treatment-A-2", "treatment-A-3", "treatment-A-4", "treatment-A-5",
    "treatment-A-6", "treatment-A-7", "treatment-A-8",
    "treatment-C-1", "treatment-C-2", "treatment-C-3", "treatment-C-4", "treatment-C-5",
    "treatment-C-6", "treatment-C-7", "treatment-C-8",
]


def load_run(rid: str) -> dict:
    score_path = DATA / "scores" / f"{rid}_sonnet.json"
    result = RunResult(**json.loads(score_path.read_text()))
    return {
        "composite": result.composite_score(WEIGHTS),
        "l1": result.l1_constraint_discovery,
        "l2": result.l2_conflict_identification,
        "l3": result.l3_score(),
        "l4": result.l4_hidden_dependencies,
    }


def mean(vals):
    return sum(vals) / len(vals) if vals else 0


def sd(vals):
    m = mean(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5 if len(vals) > 1 else 0


def cohens_d(group1, group2):
    """Cohen's d effect size (pooled SD)."""
    n1, n2 = len(group1), len(group2)
    m1, m2 = mean(group1), mean(group2)
    s1, s2 = sd(group1), sd(group2)
    pooled = (((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2)) ** 0.5
    if pooled == 0:
        return float("inf") if m1 != m2 else 0.0
    return (m2 - m1) / pooled


def mwu(x, y):
    """Mann-Whitney U via scipy. Returns (U, p_two_sided)."""
    # method='exact' for n<=8, 'asymptotic' for larger
    method = "exact" if len(x) <= 8 and len(y) <= 8 else "asymptotic"
    stat, p = mannwhitneyu(x, y, alternative="two-sided", method=method)
    return stat, p


def permutation_test_interaction(ca, cc, ta, tc, n_perms=100000):
    """Permutation test for interaction effect.

    H0: The treatment effect is the same across partitions.
    Test statistic: (mean(TC) - mean(CC)) - (mean(TA) - mean(CA))
    """
    observed = (mean(tc) - mean(cc)) - (mean(ta) - mean(ca))

    all_a = ca + ta
    all_c = cc + tc
    na = len(ca)
    nc = len(cc)

    count = 0
    for _ in range(n_perms):
        perm_a = list(all_a)
        random.shuffle(perm_a)
        perm_ca = perm_a[:na]
        perm_ta = perm_a[na:]

        perm_c = list(all_c)
        random.shuffle(perm_c)
        perm_cc = perm_c[:nc]
        perm_tc = perm_c[nc:]

        perm_stat = (mean(perm_tc) - mean(perm_cc)) - (mean(perm_ta) - mean(perm_ca))
        if abs(perm_stat) >= abs(observed):
            count += 1

    return observed, count / n_perms


# Load all data
cells = {
    "control-A": [], "control-C": [],
    "treatment-A": [], "treatment-C": [],
}

for rid in RUNS:
    d = load_run(rid)
    prefix = "-".join(rid.rsplit("-", 1)[0].split("-")[:2])
    cells[prefix].append(d)


def get_metric(cell, metric):
    return [d[metric] for d in cells[cell]]


def sig_label(p):
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "†"
    return "ns"


METRIC_LABELS = {
    "composite": "Composite",
    "l2": "L2 Conflict ID",
    "l3": "L3 Resolution",
    "l4": "L4 Hidden Dep",
}

print("=" * 70)
print("STATISTICAL ANALYSIS — SONNET 4.6 SCORING (n=8 per cell)")
print("=" * 70)

# ──────────────────────────────────────────────────────────────────────
# 1. MAIN EFFECT: ARCHITECTURE
# ──────────────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("1. MAIN EFFECT: ARCHITECTURE (Control vs Treatment, n=16 each)")
print("─" * 70)

for metric in ["composite", "l2", "l3", "l4"]:
    ctrl = get_metric("control-A", metric) + get_metric("control-C", metric)
    treat = get_metric("treatment-A", metric) + get_metric("treatment-C", metric)
    u, p = mwu(ctrl, treat)
    d = cohens_d(ctrl, treat)
    sig = sig_label(p)
    print(
        f"  {METRIC_LABELS[metric]:<16}"
        f" Control={mean(ctrl):.2f}(±{sd(ctrl):.2f})"
        f"  Treatment={mean(treat):.2f}(±{sd(treat):.2f})"
        f"  U={u:.1f}  p={p:.4f} {sig}  d={d:+.2f}"
    )

# ──────────────────────────────────────────────────────────────────────
# 2. MAIN EFFECT: PARTITION
# ──────────────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("2. MAIN EFFECT: PARTITION (A vs C, n=16 each)")
print("─" * 70)

for metric in ["composite", "l2", "l3", "l4"]:
    part_a = get_metric("control-A", metric) + get_metric("treatment-A", metric)
    part_c = get_metric("control-C", metric) + get_metric("treatment-C", metric)
    u, p = mwu(part_a, part_c)
    d = cohens_d(part_a, part_c)
    sig = sig_label(p)
    print(
        f"  {METRIC_LABELS[metric]:<16}"
        f" A={mean(part_a):.2f}(±{sd(part_a):.2f})"
        f"  C={mean(part_c):.2f}(±{sd(part_c):.2f})"
        f"  U={u:.1f}  p={p:.4f} {sig}  d={d:+.2f}"
    )

# ──────────────────────────────────────────────────────────────────────
# 3. PAIRWISE CELL COMPARISONS
# ──────────────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("3. PAIRWISE CELL COMPARISONS (n=8 each, Mann-Whitney U exact)")
print("─" * 70)

cell_names = ["control-A", "control-C", "treatment-A", "treatment-C"]
for metric in ["composite", "l3"]:
    print(f"\n  {METRIC_LABELS[metric]}:")
    for c1, c2 in combinations(cell_names, 2):
        v1 = get_metric(c1, metric)
        v2 = get_metric(c2, metric)
        u, p = mwu(v1, v2)
        d = cohens_d(v1, v2)
        sig = sig_label(p)
        print(
            f"    {c1:<13} vs {c2:<13}"
            f"  {mean(v1):.2f} vs {mean(v2):.2f}"
            f"  U={u:.1f}  p={p:.4f} {sig}  d={d:+.2f}"
        )

# ──────────────────────────────────────────────────────────────────────
# 4. INTERACTION EFFECT
# ──────────────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("4. INTERACTION EFFECT: Architecture × Partition (permutation test, 100k perms)")
print("─" * 70)

random.seed(42)

for metric in ["composite", "l2", "l3"]:
    ca = get_metric("control-A", metric)
    cc = get_metric("control-C", metric)
    ta = get_metric("treatment-A", metric)
    tc = get_metric("treatment-C", metric)

    effect_a = mean(ta) - mean(ca)
    effect_c = mean(tc) - mean(cc)
    interaction, p_int = permutation_test_interaction(ca, cc, ta, tc)

    sig = sig_label(p_int)

    print(f"\n  {METRIC_LABELS[metric]}:")
    print(
        f"    Treatment effect in Partition A: {effect_a:+.2f}"
        f"  (Treat-A {mean(ta):.2f} - Ctrl-A {mean(ca):.2f})"
    )
    print(
        f"    Treatment effect in Partition C: {effect_c:+.2f}"
        f"  (Treat-C {mean(tc):.2f} - Ctrl-C {mean(cc):.2f})"
    )
    print(f"    Interaction (C - A):             {interaction:+.2f}  p={p_int:.4f} {sig}")

# ──────────────────────────────────────────────────────────────────────
# 5. DOSE-RESPONSE
# ──────────────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("5. DOSE-RESPONSE CURVE: Treatment benefit by cross-partition conflict density")
print("─" * 70)
print()
print("  Partition A: 2/8 conflicts cross-partition (25% cross)")
print("  Partition C: 6/8 conflicts cross-partition (75% cross)")
print()

bar_scale = 40

def bar(val):
    if val >= 0:
        return " " * 20 + "│" + "█" * int(val * bar_scale)
    else:
        n = int(abs(val) * bar_scale)
        return " " * (20 - n) + "█" * n + "│"

for metric in ["composite", "l2", "l3"]:
    ca = get_metric("control-A", metric)
    cc = get_metric("control-C", metric)
    ta = get_metric("treatment-A", metric)
    tc = get_metric("treatment-C", metric)

    effect_a = mean(ta) - mean(ca)
    effect_c = mean(tc) - mean(cc)
    gradient = effect_c - effect_a
    direction = "POSITIVE" if gradient > 0 else "NEGATIVE" if gradient < 0 else "FLAT"

    print(f"  {METRIC_LABELS[metric]}:")
    print(f"    Partition A (25% cross):  effect = {effect_a:+.3f}")
    print(f"      {bar(effect_a)} {effect_a:+.2f}")
    print(f"    Partition C (75% cross):  effect = {effect_c:+.3f}")
    print(f"      {bar(effect_c)} {effect_c:+.2f}")
    print(f"    Dose-response gradient:  {gradient:+.3f} ({direction})")
    print()

# ──────────────────────────────────────────────────────────────────────
# 6. TREATMENT-C STABILITY
# ──────────────────────────────────────────────────────────────────────
print("─" * 70)
print("6. TREATMENT-C STABILITY: Runs 1-3 vs Runs 4-5 vs Runs 6-8")
print("─" * 70)

tc_early = [load_run(f"treatment-C-{i}") for i in [1, 2, 3]]
tc_mid = [load_run(f"treatment-C-{i}") for i in [4, 5]]
tc_late = [load_run(f"treatment-C-{i}") for i in [6, 7, 8]]

for metric in ["composite", "l2", "l3"]:
    early = [d[metric] for d in tc_early]
    mid = [d[metric] for d in tc_mid]
    late = [d[metric] for d in tc_late]
    print(f"  {METRIC_LABELS[metric]}:")
    early_vals = ", ".join(f"{v:.2f}" for v in early)
    mid_vals = ", ".join(f"{v:.2f}" for v in mid)
    late_vals = ", ".join(f"{v:.2f}" for v in late)
    print(f"    Runs 1-3 (n=3): {mean(early):.2f} (±{sd(early):.2f})"
          f"  values: {early_vals}")
    print(f"    Runs 4-5 (n=2): {mean(mid):.2f} (±{sd(mid):.2f})"
          f"  values: {mid_vals}")
    print(f"    Runs 6-8 (n=3): {mean(late):.2f} (±{sd(late):.2f})"
          f"  values: {late_vals}")
    print()

# ──────────────────────────────────────────────────────────────────────
# 7. SUMMARY TABLE
# ──────────────────────────────────────────────────────────────────────
print("─" * 70)
print("7. SUMMARY TABLE")
print("─" * 70)
print()
print(f"  {'Test':<45} {'Metric':<16} {'p':>8} {'Sig':>4} {'Effect':>8}")
print(f"  {'─'*45} {'─'*16} {'─'*8} {'─'*4} {'─'*8}")

summary = {}
for metric_key in ["composite", "l3"]:
    label = METRIC_LABELS[metric_key]

    # Architecture main
    ctrl = get_metric("control-A", metric_key) + get_metric("control-C", metric_key)
    treat = get_metric("treatment-A", metric_key) + get_metric("treatment-C", metric_key)
    u, p = mwu(ctrl, treat)
    d = cohens_d(ctrl, treat)
    summary[("Architecture main effect", label)] = (p, sig_label(p), d)

    # Partition main
    part_a = get_metric("control-A", metric_key) + get_metric("treatment-A", metric_key)
    part_c = get_metric("control-C", metric_key) + get_metric("treatment-C", metric_key)
    u, p = mwu(part_a, part_c)
    d = cohens_d(part_a, part_c)
    summary[("Partition main effect", label)] = (p, sig_label(p), d)

    # Interaction
    ca = get_metric("control-A", metric_key)
    cc = get_metric("control-C", metric_key)
    ta = get_metric("treatment-A", metric_key)
    tc = get_metric("treatment-C", metric_key)
    interaction, p_int = permutation_test_interaction(ca, cc, ta, tc)
    summary[("Interaction Arch×Partition", label)] = (p_int, sig_label(p_int), interaction)

    # Treatment-C vs Control-C
    u, p = mwu(cc, tc)
    d = cohens_d(cc, tc)
    summary[("Treatment-C vs Control-C", label)] = (p, sig_label(p), d)

    # Treatment-C vs Control-A
    u, p = mwu(ca, tc)
    d = cohens_d(ca, tc)
    summary[("Treatment-C vs Control-A", label)] = (p, sig_label(p), d)

tests = [
    ("Architecture main effect", "Composite"),
    ("Architecture main effect", "L3 Resolution"),
    ("Partition main effect", "Composite"),
    ("Partition main effect", "L3 Resolution"),
    ("Interaction Arch×Partition", "Composite"),
    ("Interaction Arch×Partition", "L3 Resolution"),
    ("Treatment-C vs Control-C", "Composite"),
    ("Treatment-C vs Control-C", "L3 Resolution"),
    ("Treatment-C vs Control-A", "Composite"),
    ("Treatment-C vs Control-A", "L3 Resolution"),
]

for test_name, metric_label in tests:
    p, sig, eff = summary[(test_name, metric_label)]
    eff_label = f"d={eff:+.2f}" if "Interaction" not in test_name else f"Δ={eff:+.2f}"
    print(f"  {test_name:<45} {metric_label:<16} {p:>8.4f} {sig:>4} {eff_label:>8}")
