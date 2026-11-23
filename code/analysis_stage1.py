#!/usr/bin/env python3
"""Paper #1 pilot Stage 1 analysis (Protocol S8/S9, Amendments A4/A8).
Primary: paired pass@1 (A1 - A0) on repeated-split Session-2 tasks, original
labels, recall-control pairs excluded; task-level bootstrap 95% CI (seed fixed).
Also: corrected-label subset, distance-tertile strata, acquisition rate,
token/attempt/latency tables. Reads traces_stage1_*.jsonl; writes
pilot_stage1_results.json and prints a compact summary.
"""
import csv, glob, json, pathlib, random, statistics

HF = pathlib.Path(__file__).parent
random.seed(20261122)

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
recall_qids = {int(p["session2_qid"]) for p in pairs if float(p["pair_distance"]) < 0.10}
dist_of = {int(p["session2_qid"]): float(p["pair_distance"]) for p in pairs}

traces = []
for f in glob.glob(str(HF / "traces_stage1_*.jsonl")):
    for line in open(f):
        if line.strip():
            traces.append(json.loads(line))

def pass1(rows, arm, phase, key="pass_original"):
    per = {}
    for t in rows:
        if t["arm"] == arm and t["phase"] == phase and t[key] is not None:
            per.setdefault(t["qid"], []).append(1.0 if t[key] else 0.0)
    return {q: sum(v) / len(v) for q, v in per.items()}

def paired(rows, key="pass_original", restrict=None):
    a0 = pass1(rows, "A0", "S2", key)
    a1 = pass1(rows, "A1", "S2", key)
    qs = sorted(set(a0) & set(a1))
    if restrict is not None:
        qs = [q for q in qs if q in restrict]
    diffs = [a1[q] - a0[q] for q in qs]
    return qs, diffs, a0, a1

def boot_ci(diffs, n=10000):
    if not diffs:
        return (None, None)
    m = len(diffs)
    means = []
    for _ in range(n):
        means.append(sum(diffs[random.randrange(m)] for _ in range(m)) / m)
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]

qs, diffs, a0, a1 = paired(traces)
primary_qs = [q for q in qs if q not in recall_qids]
pdiffs = [a1[q] - a0[q] for q in primary_qs]
lo, hi = boot_ci(pdiffs)
res = {
    "trajectories_total": len(traces),
    "s2_tasks_paired": len(qs),
    "primary_tasks": len(primary_qs),
    "recall_control_excluded": sorted(recall_qids),
    "A0_pass1_primary": round(statistics.mean([a0[q] for q in primary_qs]), 4) if primary_qs else None,
    "A1_pass1_primary": round(statistics.mean([a1[q] for q in primary_qs]), 4) if primary_qs else None,
    "paired_diff_primary": round(statistics.mean(pdiffs), 4) if pdiffs else None,
    "paired_diff_ci95": [round(lo, 4), round(hi, 4)] if lo is not None else None,
}
# corrected-label subset (S2 tasks with corrected gold)
l1_qs = [q for q in primary_qs
         if any(t["qid"] == q and t["pass_corrected"] is not None for t in traces)]
qs_c, diffs_c, _, _ = paired(traces, key="pass_corrected", restrict=set(l1_qs))
lo_c, hi_c = boot_ci(diffs_c)
res["corrected_subset"] = {"tasks": len(qs_c),
                           "paired_diff": round(statistics.mean(diffs_c), 4) if diffs_c else None,
                           "ci95": [round(lo_c, 4), round(hi_c, 4)] if lo_c is not None else None}
# distance tertiles
if primary_qs:
    ds = sorted(dist_of[q] for q in primary_qs)
    t1, t2 = ds[len(ds) // 3], ds[2 * len(ds) // 3]
    strata = {}
    for name, sel in [("near", lambda d: d <= t1), ("mid", lambda d: t1 < d <= t2),
                      ("far", lambda d: d > t2)]:
        sub = [a1[q] - a0[q] for q in primary_qs if sel(dist_of[q])]
        strata[name] = {"n": len(sub), "diff": round(statistics.mean(sub), 4) if sub else None}
    res["distance_strata"] = strata
# acquisition rate (A1, S1 phase): episodes / observed failures
s1 = [t for t in traces if t["arm"] == "A1" and t["phase"] == "S1"]
acq = sum(1 for t in s1 if t["acquired_episode"])
unres = sum(1 for t in s1 if t["unresolved_failure"])
res["acquisition"] = {"s1_trajectories": len(s1), "episodes": acq, "unresolved": unres,
                      "rate": round(acq / (acq + unres), 4) if (acq + unres) else None}
# tokens / attempts / latency
for arm in ("A0", "A1"):
    rows = [t for t in traces if t["arm"] == arm and t["phase"] == "S2"]
    if rows:
        res[f"{arm}_S2"] = {
            "n": len(rows),
            "mean_tokens": round(statistics.mean(t["tokens_in"] + t["tokens_out"] for t in rows), 1),
            "mean_attempts": round(statistics.mean(t["n_attempts"] for t in rows), 2),
            "mean_latency_s": round(statistics.mean(t["latency_s"] for t in rows), 1)}
# GO check (A4 margin + S9)
d, ci = res["paired_diff_primary"], res["paired_diff_ci95"]
res["GO_check"] = bool(d is not None and d >= 0.12 and ci and ci[0] > 0)
res["margin_points"] = 12
(HF / "pilot_stage1_results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
