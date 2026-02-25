"""Extract all 20 run metrics using actual Pydantic models — dual scorer."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ate_arch.models import ResolutionQuality, RubricWeights, RunResult

DATA = Path(__file__).parent.parent / "data"
WEIGHTS = RubricWeights()
SCORERS = ["haiku", "sonnet"]

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


def load_run(rid: str, scorer: str) -> dict | None:
    score_path = DATA / "scores" / f"{rid}_{scorer}.json"
    if not score_path.exists():
        return None
    result = RunResult(**json.loads(score_path.read_text()))
    l3 = result.l3_score()
    comp = result.composite_score(WEIGHTS)
    quals = list(result.l3_conflict_resolution.values())
    return {
        "composite": comp,
        "l1": result.l1_constraint_discovery,
        "l2": result.l2_conflict_identification,
        "l3": l3,
        "l4": result.l4_hidden_dependencies,
        "l3_opt": sum(1 for q in quals if q == ResolutionQuality.OPTIMAL),
        "l3_acc": sum(1 for q in quals if q == ResolutionQuality.ACCEPTABLE),
        "l3_poor": sum(1 for q in quals if q == ResolutionQuality.POOR),
        "l3_miss": sum(1 for q in quals if q == ResolutionQuality.MISSING),
    }


def mean(vals):
    return sum(vals) / len(vals) if vals else 0


def sd(vals):
    m = mean(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5 if vals else 0


# Load all data
all_data = {}
for rid in RUNS:
    all_data[rid] = {}
    for scorer in SCORERS:
        all_data[rid][scorer] = load_run(rid, scorer)

# Load metadata & comms (scorer-independent)
meta_comms = {}
for rid in RUNS:
    meta_path = DATA / "runs" / rid / "metadata.json"
    comms_path = DATA / "comms" / f"{rid}_comms.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    comms = json.loads(comms_path.read_text()) if comms_path.exists() else {}
    relay = comms.get("relay_analysis") or {}
    meta_comms[rid] = {
        "wall_clock": meta.get("wall_clock_minutes", 0),
        "interviews": meta.get("interview_count", 0),
        "total_msgs": comms.get("total_messages", 0),
        "unique_pairs": comms.get("unique_pairs", 0),
        "indirect": comms.get("has_indirect_collaboration", False),
        "relay_count": relay.get("relay_count", 0),
        "relay_sim": relay.get("mean_similarity", 0.0),
    }

# === COMPOSITE COMPARISON ===
print("=== COMPOSITE SCORES: HAIKU vs SONNET ===")
print(f"{'Run':<18} {'Haiku':>7} {'Sonnet':>7} {'Delta':>7}")
print("-" * 42)
for rid in RUNS:
    h = all_data[rid]["haiku"]
    s = all_data[rid]["sonnet"]
    hc = h["composite"] if h else float("nan")
    sc = s["composite"] if s else float("nan")
    delta = sc - hc if h and s else float("nan")
    print(f"{rid:<18} {hc:>7.2f} {sc:>7.2f} {delta:>+7.2f}")

# === PER-LAYER COMPARISON ===
for layer in ["l1", "l2", "l3", "l4"]:
    name = {"l1": "L1 Constraint Discovery", "l2": "L2 Conflict Identification",
            "l3": "L3 Resolution Quality", "l4": "L4 Hidden Dependencies"}[layer]
    print(f"\n=== {name}: HAIKU vs SONNET ===")
    print(f"{'Run':<18} {'Haiku':>7} {'Sonnet':>7} {'Delta':>7}")
    print("-" * 42)
    for rid in RUNS:
        h = all_data[rid]["haiku"]
        s = all_data[rid]["sonnet"]
        hv = h[layer] if h else float("nan")
        sv = s[layer] if s else float("nan")
        delta = sv - hv if h and s else float("nan")
        print(f"{rid:<18} {hv:>7.2f} {sv:>7.2f} {delta:>+7.2f}")

# === L3 BREAKDOWN COMPARISON ===
print("\n=== L3 RESOLUTION BREAKDOWN: HAIKU vs SONNET ===")
print(f"{'Run':<18} {'--- Haiku ---':>20} {'--- Sonnet ---':>20}")
print(
    f"{'':18} {'Opt':>4} {'Acc':>4} {'Poor':>4} {'Miss':>4}"
    f"  {'Opt':>4} {'Acc':>4} {'Poor':>4} {'Miss':>4}"
)
print("-" * 60)
for rid in RUNS:
    h = all_data[rid]["haiku"]
    s = all_data[rid]["sonnet"]
    if h and s:
        print(f"{rid:<18} {h['l3_opt']:>4} {h['l3_acc']:>4} {h['l3_poor']:>4} {h['l3_miss']:>4}"
              f"  {s['l3_opt']:>4} {s['l3_acc']:>4} {s['l3_poor']:>4} {s['l3_miss']:>4}")

# === CELL MEANS ===
print("\n=== CELL MEANS (n=5) ===")
cell_prefixes = [("control-A", "Control-A"), ("control-C", "Control-C"),
                 ("treatment-A", "Treatment-A"), ("treatment-C", "Treatment-C")]
print(f"{'Cell':<15} {'Scorer':<8} {'Comp':>6} {'SD':>5} {'L1':>6} {'L2':>6} {'L3':>6} {'L4':>6}")
print("-" * 60)
for prefix, label in cell_prefixes:
    for scorer in SCORERS:
        runs = [
            all_data[rid][scorer] for rid in RUNS
            if rid.startswith(prefix) and all_data[rid][scorer]
        ]
        comps = [r["composite"] for r in runs]
        print(f"{label:<15} {scorer:<8} {mean(comps):>6.2f} {sd(comps):>5.2f} "
              f"{mean([r['l1'] for r in runs]):>6.2f} "
              f"{mean([r['l2'] for r in runs]):>6.2f} "
              f"{mean([r['l3'] for r in runs]):>6.2f} "
              f"{mean([r['l4'] for r in runs]):>6.2f}")

# === ARCHITECTURE MEANS ===
print("\n=== ARCHITECTURE MEANS ===")
print(
    f"{'Arch':<12} {'Scorer':<8} {'n':>2} {'Comp':>6}"
    f" {'SD':>5} {'L1':>6} {'L2':>6} {'L3':>6} {'L4':>6}"
)
print("-" * 65)
for arch, label in [("control", "Control"), ("treatment", "Treatment")]:
    for scorer in SCORERS:
        runs = [
            all_data[rid][scorer] for rid in RUNS
            if rid.startswith(arch) and all_data[rid][scorer]
        ]
        comps = [r["composite"] for r in runs]
        print(f"{label:<12} {scorer:<8} {len(runs):>2} {mean(comps):>6.2f} {sd(comps):>5.2f} "
              f"{mean([r['l1'] for r in runs]):>6.2f} "
              f"{mean([r['l2'] for r in runs]):>6.2f} "
              f"{mean([r['l3'] for r in runs]):>6.2f} "
              f"{mean([r['l4'] for r in runs]):>6.2f}")

# === COMPOSITE GRID ===
print("\n=== COMPOSITE GRID ===")
for scorer in SCORERS:
    print(f"\n  {scorer.upper()}:")
    print(
        f"  {'Cell':<15} {'Run1':>6} {'Run2':>6} {'Run3':>6} {'Run4':>6}"
        f" {'Run5':>6} {'Run6':>6} {'Run7':>6} {'Run8':>6} {'Mean':>6}"
    )
    print(f"  {'-' * 53}")
    for prefix, label in cell_prefixes:
        vals = []
        parts = []
        for i in range(1, 9):
            rid = f"{prefix}-{i}"
            d = all_data[rid][scorer]
            if d:
                vals.append(d["composite"])
                parts.append(f"{d['composite']:>6.2f}")
            else:
                parts.append(f"{'N/A':>6}")
        m = mean(vals)
        print(f"  {label:<15} {' '.join(parts)} {m:>6.2f}")

# === EFFICIENCY & COMMUNICATION (scorer-independent) ===
print("\n=== EFFICIENCY & COMMUNICATION ===")
print(
    f"{'Run':<18} {'Wall(m)':>7} {'Intrvw':>6} {'Msgs':>5}"
    f" {'Pairs':>5} {'IndirC':>6} {'Relay':>5} {'RelSim':>6}"
)
print("-" * 70)
for rid in RUNS:
    d = meta_comms[rid]
    print(
        f"{rid:<18} {d['wall_clock']:>7.1f} {d['interviews']:>6}"
        f" {d['total_msgs']:>5} {d['unique_pairs']:>5}"
        f" {str(d['indirect']):>6} {d['relay_count']:>5}"
        f" {d['relay_sim']:>6.3f}"
    )
