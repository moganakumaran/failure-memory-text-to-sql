#!/usr/bin/env python3
"""Paper #1 open-model replication analysis (OpenRouter backend,
Qwen2.5-Coder-32B-Instruct; Amendment A12).
Adapts analysis_stage1.py (primary paired pass@1, bootstrap CIs, acquisition,
token/attempt tables) + the A3 contrasts of analysis_stage2.py to the
replication traces: traces_rep_A0/A1/A3_run{1..4}.jsonl (12 files).
Primary: paired pass@1 on the 97 primary repeated-split Session-2 tasks
(3 recall-control pairs excluded); corrected-label contrasts on the 49 L1
primary tasks. Writes pilot_rep_results.json and prints a compact summary.
"""
import csv, glob, json, pathlib, random, statistics

HF = pathlib.Path(__file__).parent
random.seed(20261122)

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
recall_qids = {int(p["session2_qid"]) for p in pairs if float(p["pair_distance"]) < 0.10}
assert recall_qids == {850, 1326, 1479}, recall_qids

traces = []
for pat in ("traces_rep_A0_run*.jsonl", "traces_rep_A1_run*.jsonl",
            "traces_rep_A3_run*.jsonl"):
    for f in sorted(glob.glob(str(HF / pat))):
        for line in open(f):
            if line.strip():
                traces.append(json.loads(line))

def per_arm(rows, arm, phase, key="pass_original"):
    per = {}
    for t in rows:
        if t["arm"] == arm and t["phase"] == phase and t[key] is not None:
            per.setdefault(t["qid"], []).append(1.0 if t[key] else 0.0)
    return {q: sum(v) / len(v) for q, v in per.items()}

def boot_ci(diffs, n=10000):
    if not diffs:
        return None
    m = len(diffs)
    means = sorted(sum(diffs[random.randrange(m)] for _ in range(m)) / m
                   for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)]

def paired(rows, arm_x, arm_y, phase="S2", key="pass_original", restrict=None):
    x, y = per_arm(rows, arm_x, phase, key), per_arm(rows, arm_y, phase, key)
    qs = sorted(set(x) & set(y))
    if restrict is not None:
        qs = [q for q in qs if q in restrict]
    diffs = [x[q] - y[q] for q in qs]
    return {"tasks": len(qs),
            f"{arm_x}_pass1": round(statistics.mean([x[q] for q in qs]), 4) if qs else None,
            f"{arm_y}_pass1": round(statistics.mean([y[q] for q in qs]), 4) if qs else None,
            "diff": round(statistics.mean(diffs), 4) if diffs else None,
            "ci95": boot_ci(diffs)}

s2_qids = {int(p["session2_qid"]) for p in pairs}
primary_qs = sorted(s2_qids - recall_qids)

res = {
    "model": "qwen/qwen-2.5-coder-32b-instruct",
    "backend": "openrouter",
    "trajectories_total": len(traces),
    "s2_tasks_paired": len(s2_qids),
    "primary_tasks": len(primary_qs),
    "recall_control_excluded": sorted(recall_qids),
}
# per-arm pass@1 on primary tasks (original labels)
for arm in ("A0", "A1", "A3"):
    p = per_arm(traces, arm, "S2")
    res[f"{arm}_pass1_primary"] = round(
        statistics.mean([p[q] for q in primary_qs]), 4)
# paired contrasts (original labels)
res["A1_minus_A0"] = paired(traces, "A1", "A0", restrict=set(primary_qs))
res["A3_minus_A0"] = paired(traces, "A3", "A0", restrict=set(primary_qs))
res["A3_minus_A1"] = paired(traces, "A3", "A1", restrict=set(primary_qs))
# corrected-label subset: primary S2 tasks with a corrected gold (pass_corrected not None)
l1_qs = sorted(q for q in primary_qs
               if any(t["qid"] == q and t["pass_corrected"] is not None
                      for t in traces if t["phase"] == "S2"))
res["corrected_subset"] = {"tasks": len(l1_qs)}
for arm in ("A0", "A1", "A3"):
    p = per_arm(traces, arm, "S2", key="pass_corrected")
    res["corrected_subset"][f"{arm}_pass1"] = round(
        statistics.mean([p[q] for q in l1_qs]), 4) if l1_qs else None
res["corrected_subset"]["A1_minus_A0"] = paired(
    traces, "A1", "A0", key="pass_corrected", restrict=set(l1_qs))
res["corrected_subset"]["A3_minus_A0"] = paired(
    traces, "A3", "A0", key="pass_corrected", restrict=set(l1_qs))
res["corrected_subset"]["A3_minus_A1"] = paired(
    traces, "A3", "A1", key="pass_corrected", restrict=set(l1_qs))
# A1 acquisition rate (S1 phase): episodes / (episodes + unresolved failures)
s1 = [t for t in traces if t["arm"] == "A1" and t["phase"] == "S1"]
acq = sum(1 for t in s1 if t["acquired_episode"])
unres = sum(1 for t in s1 if t["unresolved_failure"])
res["acquisition"] = {"s1_trajectories": len(s1), "episodes": acq,
                      "unresolved": unres,
                      "rate": round(acq / (acq + unres), 4) if (acq + unres) else None}
# tokens / attempts / latency per arm (S2)
for arm in ("A0", "A1", "A3"):
    rows = [t for t in traces if t["arm"] == arm and t["phase"] == "S2"]
    if rows:
        res[f"{arm}_S2"] = {
            "n": len(rows),
            "mean_tokens": round(statistics.mean(t["tokens_in"] + t["tokens_out"] for t in rows), 1),
            "mean_attempts": round(statistics.mean(t["n_attempts"] for t in rows), 2),
            "mean_latency_s": round(statistics.mean(t["latency_s"] for t in rows), 1)}
# A3 token cap (from rep_a3_cap.txt) and fallback accounting
cap = int((HF / "rep_a3_cap.txt").read_text().strip())
a3 = [t for t in traces if t["arm"] == "A3" and t["phase"] == "S2"]
res["A3_cap"] = {"cap_tokens": cap,
                 "mean_tokens": res["A3_S2"]["mean_tokens"],
                 "cap_fallback": sum(1 for t in a3 if t.get("cap_fallback")),
                 "cap_mercy": sum(1 for t in a3 if t.get("cap_mercy")),
                 "n": len(a3)}
# total replication spend
spend = json.loads((HF / "pilot_spend_replication.json").read_text())
res["spend"] = {"usd": spend["usd"], "calls": spend["calls"], "cap_usd": 10}
(HF / "pilot_rep_results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
