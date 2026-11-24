#!/usr/bin/env python3
"""B-02 re-analysis (logical review, 2026-11-24) — the missing cell.

Paper #1 reports A3-A0 = +9.8 on ORIGINAL labels over the 97 primary tasks
and A3-A0 = 0.0 on CORRECTED labels over the 49-task corrected (L1) subset.
The original-label contrast restricted to the same 49 tasks was never
computed, so the "label flip" attribution is confounded by subset
composition. This script fills that cell (and the sibling contrasts) from
the STORED Stage 1/2 traces. No model calls.

Estimator: identical to analysis_stage2.py — paired per-task run-mean
pass@1 differences, task-level bootstrap 95% CI, 10,000 resamples.
Seeding: random.seed(20261122) is reset before EACH bootstrap (the
mvr_analysis5 convention). This reproduces both published validation
cells exactly: in analysis_stage2.py the A3_vs_A0 bootstrap was the first
call on the freshly seeded stream, and mvr_analysis5 reseeded per
contrast for its corrected-label cells. Point estimates are RNG-free.

Corrected subset: the mvr_analysis5 rule — primary tasks (Session-2 qids
minus recall-control {850, 1326, 1479}) whose manifest_v2.csv row has
label_status == 'L1' and a non-empty gold_sql_corrected. Yields n = 49.

VALIDATION GATE: the script aborts unless it first reproduces
  V1  A3-A0 original, 97 tasks: diff +0.0979, CI [+0.0412, +0.1598]
      (pilot_stage2_results.json)
  V2  A3-A0 corrected, 49 tasks: diff 0.0, CI [-0.0816, +0.0816]
      (mvr_analysis5.json, mini_A3-A0_corrected/full_corrected)

Outputs: b02_subset_results.json
"""
import csv, glob, json, pathlib, random, statistics, sys

HF = pathlib.Path(__file__).parent
SEED = 20261122
RECALL_CONTROL = {850, 1326, 1479}

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
recall_qids = {int(p["session2_qid"]) for p in pairs if float(p["pair_distance"]) < 0.10}
assert recall_qids == RECALL_CONTROL, recall_qids
S2_QIDS = {int(p["session2_qid"]) for p in pairs}
PRIMARY = S2_QIDS - RECALL_CONTROL

man = list(csv.DictReader(open(HF / "manifest_v2.csv")))
by_qid = {}
for r in man:
    try:
        by_qid[int(r["source_task_id"])] = r
    except (TypeError, ValueError):
        pass

def is_l1(qid):
    r = by_qid.get(qid)
    return r is not None and r["label_status"] == "L1" and bool(r["gold_sql_corrected"])

CORR49 = sorted(q for q in PRIMARY if is_l1(q))
assert len(CORR49) == 49, len(CORR49)

def load(pattern):
    out = []
    for f in sorted(glob.glob(str(HF / pattern))):
        for line in open(f):
            if line.strip():
                out.append(json.loads(line))
    return out

def boot_ci(diffs, n=10000):
    if not diffs:
        return None
    random.seed(SEED)  # per-contrast reseed (mvr_analysis5 convention)
    m = len(diffs)
    means = sorted(sum(diffs[random.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)]

def paired(traces, arm_x, arm_y, phase, key="pass_original", restrict=None):
    """Verbatim from analysis_stage2.py."""
    def per(arm):
        d = {}
        for t in traces:
            if t["arm"] == arm and t["phase"] == phase and t[key] is not None:
                d.setdefault(t["qid"], []).append(1.0 if t[key] else 0.0)
        return {q: sum(v) / len(v) for q, v in d.items()}
    x, y = per(arm_x), per(arm_y)
    qs = sorted(set(x) & set(y))
    if restrict is not None:
        qs = [q for q in qs if q in restrict]
    diffs = [x[q] - y[q] for q in qs]
    return {"tasks": len(qs),
            f"{arm_x}_pass1": round(statistics.mean([x[q] for q in qs]), 4) if qs else None,
            f"{arm_y}_pass1": round(statistics.mean([y[q] for q in qs]), 4) if qs else None,
            "diff": round(statistics.mean(diffs), 4) if diffs else None,
            "ci95": boot_ci(diffs)}

traces = (load("traces_stage1_*.jsonl") + load("traces_stage2_A2_*.jsonl")
          + load("traces_stage2_A3_*.jsonl"))

# ---------------------------------------------------------------- validation
v1 = paired(traces, "A3", "A0", "S2", key="pass_original", restrict=PRIMARY)
v2 = paired(traces, "A3", "A0", "S2", key="pass_corrected", restrict=set(CORR49))
ok1 = (v1["tasks"] == 97 and v1["diff"] == 0.0979 and v1["ci95"] == [0.0412, 0.1598])
ok2 = (v2["tasks"] == 49 and v2["diff"] == 0.0 and v2["ci95"] == [-0.0816, 0.0816])
print("V1 A3-A0 original  n=97:", v1, "->", "REPRODUCED" if ok1 else "MISMATCH")
print("V2 A3-A0 corrected n=49:", v2, "->", "REPRODUCED" if ok2 else "MISMATCH")
if not (ok1 and ok2):
    print("VALIDATION FAILED — aborting; no new numbers written.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------- new cells
R = {"validation": {"V1_A3-A0_original_97": v1, "V2_A3-A0_corrected_49": v2,
                    "both_reproduced": True},
     "corrected_subset_qids": CORR49,
     "original_labels_on_corrected_subset_49": {
         "A3-A0": paired(traces, "A3", "A0", "S2", key="pass_original", restrict=set(CORR49)),
         "A3-A1": paired(traces, "A3", "A1", "S2", key="pass_original", restrict=set(CORR49)),
         "A1-A0": paired(traces, "A1", "A0", "S2", key="pass_original", restrict=set(CORR49)),
         "A2-A0": paired(traces, "A2", "A0", "S2", key="pass_original", restrict=set(CORR49)),
     }}
new = R["original_labels_on_corrected_subset_49"]["A3-A0"]
R["decomposition_A3-A0"] = {
    "original_97": v1["diff"], "original_49": new["diff"], "corrected_49": v2["diff"],
    "subset_component_pts": round((new["diff"] - v1["diff"]) * 100, 2),
    "label_component_pts": round((v2["diff"] - new["diff"]) * 100, 2),
    "total_change_pts": round((v2["diff"] - v1["diff"]) * 100, 2),
    "note": "total = subset component (97 -> 49 tasks, original labels) + "
            "label component (original -> corrected, same 49 tasks). "
            "Components are point-estimate arithmetic on nested contrasts."}
(HF / "b02_subset_results.json").write_text(json.dumps(R, indent=1))
print(json.dumps(R, indent=1))
