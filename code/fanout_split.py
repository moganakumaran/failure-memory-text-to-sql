#!/usr/bin/env python3
"""FanOut split of the B-02 label flip (morning brief 2026-11-24, Paper #1 angle).

Question: does the +10.2 -> 0.0 label flip on the 49-task corrected subset
come from the fan-out-defective tasks inside it, or from the rest?

Groups (from fanout_crosscheck_results.json, qid join verified: db matches
127/127 on the 2025 list, question matches 116/127 with 11 release
rewordings, none of them in the overlap):
- FANOUT strict: June-2024 pilot 'inflated' inside the 49: {1037, 1243, 1490}
- FANOUT broad: strict + dev-2025 'fixed_in_release' inside the 49: {273}
- REST: the other 45 of the 49.
- CONTROLS ('intended', gold correct): {208, 1040} — reported separately.

Estimator: identical to analysis_b02_subset.py (paired per-task run-mean
pass@1 differences, task-level bootstrap 95% CI, 10,000 resamples,
random.seed(20261122) reset per contrast). Same validation gate (V1/V2
must reproduce exactly) or the script aborts with no output written.
Small-n warning: n=3/4 groups cannot support inference; their rows are
descriptive (point estimates + each task's own diff + the group's
contribution to the 49-task total in points). No model calls.
"""
import csv, glob, json, pathlib, random, statistics, sys

HF = pathlib.Path(__file__).parent
SEED = 20261122
RECALL_CONTROL = {850, 1326, 1479}

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
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
assert CORR49 == json.loads((HF / "b02_subset_results.json").read_text())["corrected_subset_qids"]

STRICT = {1037, 1243, 1490}
BROAD = {273, 1037, 1243, 1490}
CONTROLS = {208, 1040}
assert STRICT <= set(CORR49) and BROAD <= set(CORR49) and CONTROLS <= set(CORR49)
REST = sorted(set(CORR49) - BROAD)
REST_STRICT = sorted(set(CORR49) - STRICT)

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
    random.seed(SEED)
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
            "ci95": boot_ci(diffs),
            "per_task_diffs": {str(q): round(x[q] - y[q], 4) for q in qs}}

traces = (load("traces_stage1_*.jsonl") + load("traces_stage2_A2_*.jsonl")
          + load("traces_stage2_A3_*.jsonl"))

v1 = paired(traces, "A3", "A0", "S2", key="pass_original", restrict=PRIMARY)
v2 = paired(traces, "A3", "A0", "S2", key="pass_corrected", restrict=set(CORR49))
ok1 = (v1["tasks"] == 97 and v1["diff"] == 0.0979 and v1["ci95"] == [0.0412, 0.1598])
ok2 = (v2["tasks"] == 49 and v2["diff"] == 0.0 and v2["ci95"] == [-0.0816, 0.0816])
print("V1:", "REPRODUCED" if ok1 else "MISMATCH", "| V2:", "REPRODUCED" if ok2 else "MISMATCH")
if not (ok1 and ok2):
    print("VALIDATION FAILED — aborting; no new numbers written.", file=sys.stderr)
    sys.exit(1)

def group(name, qids, key):
    r = paired(traces, "A3", "A0", "S2", key=key, restrict=set(qids))
    contrib_pts = round(sum(r["per_task_diffs"].values()) / 49 * 100, 2)
    return {"group": name, "n": len(qids), "key": key,
            "A3_pass1": r["A3_pass1"], "A0_pass1": r["A0_pass1"],
            "diff": r["diff"], "ci95": r["ci95"],
            "per_task_diffs": r["per_task_diffs"],
            "contribution_to_49_total_pts": contrib_pts}

R = {"validation": {"V1": v1["diff"], "V2": v2["diff"], "both_reproduced": True},
     "groups": {
         "fanout_broad_n4_original": group("fanout_broad", sorted(BROAD), "pass_original"),
         "fanout_broad_n4_corrected": group("fanout_broad", sorted(BROAD), "pass_corrected"),
         "rest_n45_original": group("rest45", REST, "pass_original"),
         "rest_n45_corrected": group("rest45", REST, "pass_corrected"),
         "fanout_strict_n3_original": group("fanout_strict", sorted(STRICT), "pass_original"),
         "fanout_strict_n3_corrected": group("fanout_strict", sorted(STRICT), "pass_corrected"),
         "controls_n2_original": group("controls_intended", sorted(CONTROLS), "pass_original"),
         "controls_n2_corrected": group("controls_intended", sorted(CONTROLS), "pass_corrected"),
         "all49_original": group("all49", CORR49, "pass_original"),
         "all49_corrected": group("all49", CORR49, "pass_corrected"),
     },
     "note": ("Per-group CIs at n=3/4 are descriptive only; no inference is "
              "drawn from them. contribution_to_49_total_pts = sum of the "
              "group's per-task diffs / 49, in points — the group's share of "
              "the 49-task total contrast.")}
(HF / "fanout_split_results.json").write_text(json.dumps(R, indent=1))
print(json.dumps(R, indent=1))
