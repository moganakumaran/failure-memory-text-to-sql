#!/usr/bin/env python3
"""Paper #1 pilot Stage 2 analysis (Amendment A9).
Contrasts: A3 and A2 vs A0/A1 on the repeated split (paired pass@1, S2,
recall-control excluded); drift split A0/A1/A4 (paired pass@1 on drift-phase
tasks, overall and by silent/overt). Bootstrap CIs, seed fixed.
"""
import csv, glob, json, pathlib, random, statistics

HF = pathlib.Path(__file__).parent
random.seed(20261122)

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
recall_qids = {int(p["session2_qid"]) for p in pairs if float(p["pair_distance"]) < 0.10}
spec = {int(s["qid"]): s for s in csv.DictReader(open(HF / "drift_spec.csv"))}

def load(pattern):
    out = []
    for f in glob.glob(str(HF / pattern)):
        for line in open(f):
            if line.strip():
                out.append(json.loads(line))
    return out

def boot_ci(diffs, n=10000):
    if not diffs:
        return None
    m = len(diffs)
    means = sorted(sum(diffs[random.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)]

def paired(traces, arm_x, arm_y, phase, key="pass_original", restrict=None):
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

res = {}
rep = load("traces_stage1_*.jsonl") + load("traces_stage2_A2_*.jsonl") + load("traces_stage2_A3_*.jsonl")
primary = set(range(100000)) - recall_qids  # restrict via qid set below
s2_qids = {int(p["session2_qid"]) for p in pairs} - recall_qids
res["A3_vs_A0"] = paired(rep, "A3", "A0", "S2", restrict=s2_qids)
res["A3_vs_A1"] = paired(rep, "A3", "A1", "S2", restrict=s2_qids)
res["A2_vs_A0"] = paired(rep, "A2", "A0", "S2", restrict=s2_qids)
res["A2_vs_A1"] = paired(rep, "A2", "A1", "S2", restrict=s2_qids)
a3 = [t for t in rep if t["arm"] == "A3" and t["phase"] == "S2"]
if a3:
    res["A3_S2_cost"] = {"n": len(a3),
                         "mean_tokens": round(statistics.mean(t["tokens_in"] + t["tokens_out"] for t in a3), 1),
                         "mean_attempts": round(statistics.mean(t["n_attempts"] for t in a3), 2)}

drift = load("traces_stage2_drift_*.jsonl")
res["drift_all"] = {c: paired(drift, a, b, "drift")
                    for c, (a, b) in {"A1-A0": ("A1", "A0"), "A4-A0": ("A4", "A0"),
                                      "A4-A1": ("A4", "A1")}.items()}
silent = {q for q, s in spec.items() if s["drift_type"] == "silent"}
overt = {q for q, s in spec.items() if s["drift_type"] == "overt"}
res["drift_silent_A4-A0"] = paired(drift, "A4", "A0", "drift", restrict=silent)
res["drift_overt_A4-A0"] = paired(drift, "A4", "A0", "drift", restrict=overt)
res["drift_silent_A1-A0"] = paired(drift, "A1", "A0", "drift", restrict=silent)
res["drift_overt_A1-A0"] = paired(drift, "A1", "A0", "drift", restrict=overt)
res["trajectories"] = {"repeated_stage2": len(rep), "drift": len(drift)}
(HF / "pilot_stage2_results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
