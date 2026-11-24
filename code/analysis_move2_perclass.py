#!/usr/bin/env python3
"""Move 2 (2026-11-24) — per-failure-class memory effect, Paper #1.

QUESTION: on the repeated-failure split (S2, 97 primary tasks), does the
memory effect (A1-A0 paired pass@1) differ by failure class? Headline is
-1.8 pts overall; this checks whether the average hides per-class effects.

GROUPING (pre-committed): each S2 task is grouped by the failure class of
the failure its PAIRED Session-1 task produced (splits_repeated.csv
session1_qid) — the class of the recurring failure the memory was meant
to address, fixed before S2 ran. Never by the S2 failure's own class.

LABEL SOURCES, priority order:
  (1) Paper #2 coding pass reconciled human label for that
      (task, split='repeated', phase='S1') failure
      (paper2_coding_manifest.jsonl + paper2_coding_reconciled.jsonl).
      F1a/F1b are folded into the F1 family (composition logged).
  (2) Episode-journal fingerprint class. NOTE: the A1 S1 journals carry
      no qid and every one of the 100 S1 episodes is class F6 (the
      heuristic class is derived from the error signature and is
      degenerate for verifier-rejected failures), so the journal
      fallback group is F6 by construction.
Tasks whose paired S1 task produced NO acquired episode in any A1 S1 run
(traces_stage1_A1_*.jsonl acquired_episode flag; 100 episodes over 47
distinct S1 qids) form the 'no episode' stratum — reported, never dropped.

ESTIMATOR: identical to analysis_stage2.py / analysis_b02_subset.py —
paired per-task run-mean pass@1, task-level bootstrap 95% CI, 10,000
resamples, random.seed(20261122) reset before each bootstrap.

VALIDATION GATE: per-class diffs weighted by task counts (incl. the
no-episode stratum) must recombine to the published headlines
A1-A0 = -0.018 and A2-A0 = -0.0464 (-4.6 pts) on the 97 (original labels). The script
aborts without writing results if recombination fails.

No model calls. Outputs: move2_perclass_results.json
"""
import csv, glob, json, pathlib, random, statistics, sys
from collections import Counter, defaultdict

HF = pathlib.Path(__file__).parent
SEED = 20261122
RECALL_CONTROL = {850, 1326, 1479}

# ------------------------------------------------------------------ tasks
pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
S2_TO_S1 = {int(p["session2_qid"]): int(p["session1_qid"]) for p in pairs}
PRIMARY = sorted(set(S2_TO_S1) - RECALL_CONTROL)
assert len(PRIMARY) == 97

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

# ------------------------------------------------------------------ labels
manifest = [json.loads(l) for l in open(HF / "paper2_coding_manifest.jsonl")]
recon = {}
for l in open(HF / "paper2_coding_reconciled.jsonl"):
    r = json.loads(l)
    recon[r["item_id"]] = r
coding_label = {}   # s1 qid -> (primary_class, secondary_class)
for m in manifest:
    if m["split"] == "repeated" and m["phase"] == "S1":
        r = recon[m["item_id"]]
        coding_label[m["qid"]] = (r["primary_class"], r.get("secondary_class"))

def load(pattern):
    out = []
    for f in sorted(glob.glob(str(HF / pattern))):
        for line in open(f):
            if line.strip():
                out.append(json.loads(line))
    return out

# acquisition: S1 qid -> set of runs with an acquired episode (A1, S1)
acq_runs = defaultdict(set)
for t in load("traces_stage1_A1_*.jsonl"):
    if t["phase"] == "S1" and t.get("acquired_episode"):
        acq_runs[t["qid"]].add(t["run_id"])
n_episodes = sum(1 for t in load("traces_stage1_A1_*.jsonl")
                 if t["phase"] == "S1" and t.get("acquired_episode"))
assert n_episodes == 100, n_episodes

# journal class check (degenerate heuristic — verify, don't assume)
jclasses = Counter()
for f in sorted(glob.glob(str(HF / "episodes_stage1_A1_run*.jsonl"))):
    for line in open(f):
        r = json.loads(line)
        if r["phase"] == "S1":
            jclasses[r["episode"]["failure_class"]] += 1
assert jclasses == Counter({"F6": 100}), jclasses

def family(cls):
    return "F1" if cls in ("F1a", "F1b") else cls

# ------------------------------------------------------------------ groups
groups = {}          # s2 qid -> group label
group_source = {}    # s2 qid -> 'human' | 'journal' | 'no_episode'
ambiguity = []
for s2 in PRIMARY:
    s1 = S2_TO_S1[s2]
    if s1 not in acq_runs:
        groups[s2] = "no episode"
        group_source[s2] = "no_episode"
        continue
    if s1 in coding_label:
        cls, sec = coding_label[s1]
        groups[s2] = family(cls)
        group_source[s2] = "human"
        if cls in ("F1a", "F1b"):
            ambiguity.append({"s2_qid": s2, "s1_qid": s1, "issue": "subtype_folded",
                              "detail": f"coded {cls} (secondary={sec}); grouped as F1"})
        elif sec:
            ambiguity.append({"s2_qid": s2, "s1_qid": s1, "issue": "secondary_class_present",
                              "detail": f"primary={cls}, secondary={sec}; grouped by primary"})
    else:
        groups[s2] = "F6"          # journal fallback: uniform heuristic class
        group_source[s2] = "journal"
        ambiguity.append({"s2_qid": s2, "s1_qid": s1, "issue": "no_coding_label",
                          "detail": "episode acquired but no coding-pass item; journal class F6 used"})
    if 0 < len(acq_runs[s1]) < 4:
        ambiguity.append({"s2_qid": s2, "s1_qid": s1, "issue": "partial_acquisition",
                          "detail": f"episode acquired in {len(acq_runs[s1])}/4 A1 S1 runs; grouped as has-episode"})

group_members = defaultdict(list)
for s2 in PRIMARY:
    group_members[groups[s2]].append(s2)
coverage = Counter(group_source.values())

# ------------------------------------------------------------------ estimator
def boot_ci(diffs, n=10000):
    if not diffs:
        return None
    random.seed(SEED)
    m = len(diffs)
    means = sorted(sum(diffs[random.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)]

def paired(traces, arm_x, arm_y, key="pass_original", restrict=None):
    def per(arm):
        d = {}
        for t in traces:
            if t["arm"] == arm and t["phase"] == "S2" and t[key] is not None:
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

mini = load("traces_stage1_*.jsonl") + load("traces_stage2_A2_*.jsonl")
rep = load("traces_rep_A0_*.jsonl") + load("traces_rep_A1_*.jsonl")

# ------------------------------------------------------------------ gate
overall_a1 = paired(mini, "A1", "A0", restrict=set(PRIMARY))
overall_a2 = paired(mini, "A2", "A0", restrict=set(PRIMARY))
print("overall A1-A0:", overall_a1)
print("overall A2-A0:", overall_a2)

def per_group(traces, arm_x, arm_y, key, restrict_all):
    out = {}
    for g, members in sorted(group_members.items()):
        r = set(members) & restrict_all
        out[g] = paired(traces, arm_x, arm_y, key=key, restrict=r) if r else None
    return out

def recombine(per):
    num = sum(v["tasks"] * v["diff"] for v in per.values() if v and v["diff"] is not None)
    den = sum(v["tasks"] for v in per.values() if v and v["diff"] is not None)
    return round(num / den, 4) if den else None

pg_a1 = per_group(mini, "A1", "A0", "pass_original", set(PRIMARY))
pg_a2 = per_group(mini, "A2", "A0", "pass_original", set(PRIMARY))
rec_a1, rec_a2 = recombine(pg_a1), recombine(pg_a2)
print("recombined A1-A0:", rec_a1, "| recombined A2-A0:", rec_a2)
gate_ok = (overall_a1["diff"] == -0.018 and overall_a2["diff"] == -0.0464
           and rec_a1 == overall_a1["diff"] and rec_a2 == overall_a2["diff"])
if not gate_ok:
    print("VALIDATION GATE FAILED — no results written.", file=sys.stderr)
    sys.exit(1)
print("VALIDATION GATE PASSED")

# ------------------------------------------------------------------ results
R = {
    "question": "Per-failure-class A1-A0 (memory effect) on the 97 primary repeated-failure tasks",
    "grouping_rule": "S2 task grouped by the reconciled class of its paired S1 task's failure "
                     "(coding pass first; journal fingerprint class as fallback); S1 tasks with "
                     "no acquired episode in any A1 S1 run form the 'no episode' stratum.",
    "validation_gate": {"overall_A1-A0": overall_a1, "overall_A2-A0": overall_a2,
                        "recombined_A1-A0": rec_a1, "recombined_A2-A0": rec_a2,
                        "published": {"A1-A0": -0.018, "A2-A0": -0.0464}, "passed": True},
    "coverage": {"of_97": dict(coverage),
                 "s1_episodes_total": n_episodes,
                 "s1_qids_with_episode": len(acq_runs),
                 "journal_S1_classes": dict(jclasses)},
    "group_sizes": {g: len(m) for g, m in sorted(group_members.items())},
    "mini_A1-A0_original_by_class": pg_a1,
    "mini_A1-A0_corrected_by_class": per_group(mini, "A1", "A0", "pass_corrected", set(CORR49)),
    "mini_A2-A0_original_by_class": pg_a2,
    "mini_A2-A0_corrected_by_class": per_group(mini, "A2", "A0", "pass_corrected", set(CORR49)),
    "rep_A1-A0_original_by_class": per_group(rep, "A1", "A0", "pass_original", set(PRIMARY)),
    "rep_A1-A0_corrected_by_class": per_group(rep, "A1", "A0", "pass_corrected", set(CORR49)),
    "overall_corrected_A1-A0_49": paired(mini, "A1", "A0", key="pass_corrected", restrict=set(CORR49)),
    "ambiguity_list": ambiguity,
    "group_members": {g: m for g, m in sorted(group_members.items())},
    "group_source_by_qid": {str(q): group_source[q] for q in PRIMARY},
}
json.dump(R, open(HF / "move2_perclass_results.json", "w"), indent=1)
print("coverage:", dict(coverage))
print("group sizes:", R["group_sizes"])
print("wrote move2_perclass_results.json")
