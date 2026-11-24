#!/usr/bin/env python3
"""MVR Workstream A5 — changed-gold accounting (PVLDB panel fix item 5).

Existing data only; NO model calls. For every corrected-label contrast
reported in Paper #1 (main.tex S5), recompute the contrast restricted to
tasks whose Jin et al. corrected gold SQL actually DIFFERS from the original
BIRD gold ("changed-gold" tasks), using the same paired per-task run-mean
pass@1 estimator and task-level bootstrap 95% CI (10,000 resamples) as
analysis_stage1.py / analysis_stage2.py / analysis_a14.py / analysis_rep.py /
analysis_fixes.py.

Changed-gold rule (deterministic): a task is L1 (corrected label available,
label_status == 'L1' in manifest_v2.csv, gold_sql_corrected non-empty) and
    normalize(gold_sql_original) != normalize(gold_sql_corrected)
where normalize = lowercase, collapse all whitespace runs to a single space,
strip leading/trailing whitespace. Sanity: this rule yields 220 changed of
498 L1 tasks overall, exactly the count stated in main.tex S3.1; a raw
exact-string comparison yields the same 220.

Bootstrap seeding note: the original scripts share one RNG stream across
contrasts, so their published CIs depend on stream position. Here each
contrast reseeds random.seed(20261122) before its bootstrap, making every
number independently reproducible from this script alone. Point estimates
are exact (RNG-free); full-subset CIs may differ from the published ones in
the 3rd-4th decimal for that reason alone (checked in the report).

Also: execution-equivalence check for changed-gold tasks in the relevant
subsets — original vs corrected gold executed (read-only) on the original
BIRD database; a string difference whose two golds return equal results
(under pilot_lib.results_equal semantics) does NOT change any score.

Outputs: mvr_analysis5.json (machine-readable). The .md report is written
by hand from these numbers.
"""
import csv, glob, json, math, pathlib, random, re, sqlite3, statistics, time
from collections import defaultdict

HF = pathlib.Path(__file__).parent
SEED = 20261122
RECALL_CONTROL = {850, 1326, 1479}
DBROOT = HF / "datasets/bird/dev_20240627/dev_databases/dev_databases"

# ---------------------------------------------------------------- manifest
man = list(csv.DictReader(open(HF / "manifest_v2.csv")))
by_qid = {}
for r in man:
    try:
        by_qid[int(r["source_task_id"])] = r
    except (TypeError, ValueError):
        pass

def normalize(sql):
    return re.sub(r"\s+", " ", (sql or "").strip().lower())

def gold_class(qid):
    """'changed' | 'audited-unchanged' | 'no-corrected-label'"""
    r = by_qid.get(qid)
    if r is None or r["label_status"] != "L1" or not r["gold_sql_corrected"]:
        return "no-corrected-label"
    return ("changed" if normalize(r["gold_sql_original"]) != normalize(r["gold_sql_corrected"])
            else "audited-unchanged")

L1_ALL = [q for q in by_qid if gold_class(q) != "no-corrected-label"]
CHANGED_ALL = sorted(q for q in L1_ALL if gold_class(q) == "changed")

pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
S2_QIDS = {int(p["session2_qid"]) for p in pairs}
PRIMARY = sorted(S2_QIDS - RECALL_CONTROL)
CORR_PRIMARY = sorted(q for q in PRIMARY if gold_class(q) != "no-corrected-label")
CHANGED_PRIMARY = sorted(q for q in CORR_PRIMARY if gold_class(q) == "changed")
UNCHANGED_PRIMARY = sorted(q for q in CORR_PRIMARY if gold_class(q) == "audited-unchanged")
UNCORRECTED_PRIMARY = sorted(q for q in PRIMARY if gold_class(q) == "no-corrected-label")

spec = {int(s["qid"]): s for s in csv.DictReader(open(HF / "drift_spec.csv"))}
DRIFT_QIDS = sorted(spec)
CHANGED_DRIFT = sorted(q for q in DRIFT_QIDS if gold_class(q) == "changed")
UNCHANGED_DRIFT = sorted(q for q in DRIFT_QIDS if gold_class(q) == "audited-unchanged")
SILENT = sorted(q for q in DRIFT_QIDS if spec[q]["drift_type"] == "silent")
OVERT = sorted(q for q in DRIFT_QIDS if spec[q]["drift_type"] == "overt")

# ---------------------------------------------------------------- traces
def load(patterns, phase=None, arm=None):
    rows = []
    for pat in patterns:
        for f in sorted(glob.glob(str(HF / pat))):
            if "starved" in f or "smoke" in f:
                continue
            for line in open(f):
                if line.strip():
                    t = json.loads(line)
                    if phase and t.get("phase") != phase:
                        continue
                    if arm and t.get("arm") != arm:
                        continue
                    rows.append(t)
    return rows

def per_task(rows, label):
    d = defaultdict(list)
    for t in rows:
        v = t.get(label)
        if v is not None:
            d[t["qid"]].append(1.0 if v else 0.0)
    return {q: sum(v) / len(v) for q, v in d.items()}

def boot_ci(diffs):
    """Mirror of analysis_stage1.boot_ci (10k resamples, 2.5/97.5 pct)."""
    if not diffs:
        return None
    random.seed(SEED)
    m = len(diffs)
    means = sorted(sum(diffs[random.randrange(m)] for _ in range(m)) / m
                   for _ in range(10000))
    return [round(means[int(0.025 * 10000)], 4), round(means[int(0.975 * 10000)], 4)]

def paired(rows_x, rows_y, label="pass_corrected", restrict=None):
    """x minus y, paired per-task run-mean differences (analysis_stage2 style)."""
    x, y = per_task(rows_x, label), per_task(rows_y, label)
    qs = sorted(set(x) & set(y))
    if restrict is not None:
        qs = [q for q in qs if q in restrict]
    diffs = [x[q] - y[q] for q in qs]
    return {"tasks": len(qs), "qids": qs,
            "x_pass1": round(statistics.mean([x[q] for q in qs]), 4) if qs else None,
            "y_pass1": round(statistics.mean([y[q] for q in qs]), 4) if qs else None,
            "diff": round(statistics.mean(diffs), 4) if diffs else None,
            "ci95": boot_ci(diffs)}

def contrast_block(rows_x, rows_y, subset, changed, label="pass_corrected"):
    full = paired(rows_x, rows_y, label, restrict=set(subset))
    chg = paired(rows_x, rows_y, label, restrict=set(changed))
    unc = paired(rows_x, rows_y, label, restrict=set(subset) - set(changed))
    for d in (full, chg, unc):
        d.pop("qids", None)
    return {"subset_n": full["tasks"], "changed_n": chg["tasks"],
            "unchanged_n": unc["tasks"],
            "full_corrected": full, "changed_only": chg, "unchanged_only": unc}

def passk_diffs(rows_x, rows_y, label, tasks, k):
    """fixes.boot_diff with k: per-task tau-bench pass^k estimator diffs (y - x
    in fixes; here x - y to match the contrast direction of this script —
    callers pass (A0rows, A1rows) style accordingly)."""
    def per(rows):
        d = defaultdict(list)
        for t in rows:
            if t["qid"] not in tasks:
                continue
            v = t.get(label)
            if v is not None:
                d[t["qid"]].append(1 if v else 0)
        return d
    dx, dy = per(rows_x), per(rows_y)
    common = sorted(set(dx) & set(dy))
    def val(runs):
        n, c = len(runs), sum(runs)
        return math.comb(c, k) / math.comb(n, k) if n >= k else None
    diffs = []
    for q in common:
        vx, vy = val(dx[q]), val(dy[q])
        if vx is not None and vy is not None:
            diffs.append(vx - vy)
    return diffs

# load all trace families (per-arm patterns exactly as the original scripts)
mini = {a: load([f"traces_stage1_{a}_run*.jsonl"], phase="S2") if a in ("A0", "A1")
        else load([f"traces_stage2_{a}_run*.jsonl"], phase="S2")
        for a in ("A0", "A1", "A2", "A3")}
rep = {a: load([f"traces_rep_{a}_run*.jsonl"], phase="S2") for a in ("A0", "A1", "A3")}
abl = {a: load([f"traces_abl_{a}_run*.jsonl"], phase="S2") for a in ("A0", "A1")}
drift_rows = load(["traces_stage2_drift_run*.jsonl"], phase="drift")
drift = {a: [t for t in drift_rows if t["arm"] == a] for a in ("A0", "A1", "A4")}
fix_ctrl = load(["traces_fix_ctrl_run*.jsonl"], phase="undrifted", arm="A0")
drift_a0 = [t for t in drift_rows if t["arm"] == "A0"]

R = {"rule": "changed iff label_status=='L1' and normalize(gold_sql_original) != "
             "normalize(gold_sql_corrected); normalize = lowercase + whitespace-collapse + strip",
     "overall_L1": {"tasks": len(L1_ALL), "changed": len(CHANGED_ALL),
                    "audited_unchanged": len(L1_ALL) - len(CHANGED_ALL),
                    "changed_exact_string_rule": sum(
                        1 for q in L1_ALL
                        if by_qid[q]["gold_sql_original"] != by_qid[q]["gold_sql_corrected"])},
     "primary_corrected_subset": {"n": len(CORR_PRIMARY), "qids": CORR_PRIMARY,
                                  "changed_n": len(CHANGED_PRIMARY), "changed_qids": CHANGED_PRIMARY,
                                  "unchanged_n": len(UNCHANGED_PRIMARY), "unchanged_qids": UNCHANGED_PRIMARY},
     "primary_uncorrected": {"n": len(UNCORRECTED_PRIMARY), "qids": UNCORRECTED_PRIMARY},
     "drift_subset": {"n": len(DRIFT_QIDS), "qids": DRIFT_QIDS,
                      "changed_n": len(CHANGED_DRIFT), "changed_qids": CHANGED_DRIFT,
                      "unchanged_n": len(UNCHANGED_DRIFT), "unchanged_qids": UNCHANGED_DRIFT},
     "contrasts": {}}

C = R["contrasts"]
# ---- repeated split, main study (mini) ----
C["mini_A1-A0_corrected"] = contrast_block(mini["A1"], mini["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
C["mini_A3-A0_corrected"] = contrast_block(mini["A3"], mini["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
C["mini_A3-A1_corrected"] = contrast_block(mini["A3"], mini["A1"], CORR_PRIMARY, CHANGED_PRIMARY)
C["mini_A2-A0_corrected"] = contrast_block(mini["A2"], mini["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
C["mini_A2-A1_corrected"] = contrast_block(mini["A2"], mini["A1"], CORR_PRIMARY, CHANGED_PRIMARY)
# ---- verifier ablation (A14), corrected ----
C["ablation_A1-A0_corrected"] = contrast_block(abl["A1"], abl["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
# ---- pass^k corrected, mini A1-A0 (fixes estimator) ----
pk = {}
for k in (2, 4):
    for name, tasks in (("full_corrected", set(CORR_PRIMARY)),
                        ("changed_only", set(CHANGED_PRIMARY)),
                        ("unchanged_only", set(UNCHANGED_PRIMARY))):
        diffs = passk_diffs(mini["A1"], mini["A0"], "pass_corrected", tasks, k)
        pk[f"pass^{k}_{name}"] = {"tasks": len(diffs),
                                  "diff": round(statistics.mean(diffs), 4) if diffs else None,
                                  "ci95": boot_ci(diffs)}
C["mini_A1-A0_corrected_passk"] = pk
# ---- replication (Qwen) ----
C["rep_A1-A0_corrected"] = contrast_block(rep["A1"], rep["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
C["rep_A3-A0_corrected"] = contrast_block(rep["A3"], rep["A0"], CORR_PRIMARY, CHANGED_PRIMARY)
C["rep_A3-A1_corrected"] = contrast_block(rep["A3"], rep["A1"], CORR_PRIMARY, CHANGED_PRIMARY)
# ---- drift ----
# A14 paired drift effect, corrected view: drifted A0 minus undrifted A0
C["drift_effect_A0_corrected"] = contrast_block(drift_a0, fix_ctrl, DRIFT_QIDS, CHANGED_DRIFT)
C["drift_A1-A0_corrected"] = contrast_block(drift["A1"], drift["A0"], DRIFT_QIDS, CHANGED_DRIFT)
C["drift_A4-A0_corrected"] = contrast_block(drift["A4"], drift["A0"], DRIFT_QIDS, CHANGED_DRIFT)
C["drift_A4-A1_corrected"] = contrast_block(drift["A4"], drift["A1"], DRIFT_QIDS, CHANGED_DRIFT)
# supplementary (NOT separately reported in the paper): silent/overt corrected
C["drift_silent_A4-A0_corrected_SUPPLEMENTARY"] = contrast_block(
    drift["A4"], drift["A0"], SILENT, [q for q in CHANGED_DRIFT if q in set(SILENT)])
C["drift_silent_A1-A0_corrected_SUPPLEMENTARY"] = contrast_block(
    drift["A1"], drift["A0"], SILENT, [q for q in CHANGED_DRIFT if q in set(SILENT)])
C["drift_overt_A4-A0_corrected_SUPPLEMENTARY"] = contrast_block(
    drift["A4"], drift["A0"], OVERT, [q for q in CHANGED_DRIFT if q in set(OVERT)])
C["drift_effect_silent_A0_corrected_SUPPLEMENTARY"] = contrast_block(
    drift_a0, fix_ctrl, SILENT, [q for q in CHANGED_DRIFT if q in set(SILENT)])
C["drift_effect_overt_A0_corrected_SUPPLEMENTARY"] = contrast_block(
    drift_a0, fix_ctrl, OVERT, [q for q in CHANGED_DRIFT if q in set(OVERT)])

# ---- 49 vs 48 resolution data ----
def corr_set(rows_by_arm_patterns, phase):
    rows = load(rows_by_arm_patterns, phase=phase)
    return sorted({t["qid"] for t in rows if t.get("pass_corrected") is not None})
stage1_all = corr_set(["traces_stage1_*.jsonl"], "S2")
rep_all = corr_set(["traces_rep_A0_run*.jsonl", "traces_rep_A1_run*.jsonl",
                    "traces_rep_A3_run*.jsonl"], "S2")
R["n49_vs_48"] = {
    "stage1_corrected_qids_all100": stage1_all,
    "replication_corrected_qids_all100": rep_all,
    "sets_identical_all100": stage1_all == rep_all,
    "stage1_corrected_primary_n": len([q for q in stage1_all if q in set(PRIMARY)]),
    "replication_corrected_primary_n": len([q for q in rep_all if q in set(PRIMARY)]),
    "recall_control_in_corrected_set": sorted(set(stage1_all) & RECALL_CONTROL),
    "primary_total": len(PRIMARY),
    "primary_with_corrected": len(CORR_PRIMARY),
    "primary_without_corrected": len(UNCORRECTED_PRIMARY),
    "note": "97 primary = 49 with corrected labels (L1) + 48 without (L2). "
            "Stage 1 and replication corrected subsets are the SAME 49 tasks."}

# ---- execution equivalence for changed-gold tasks (primary + drift) ----
def exec_rows(db, sql):
    path = DBROOT / db / f"{db}.sqlite"
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    deadline = time.time() + 10
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
    try:
        return con.execute(sql).fetchmany(100000), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        con.close()

def results_equal(pred, gold, gold_sql):
    if pred is None or gold is None:
        return False
    if "order by" in gold_sql.lower():
        return [tuple(map(str, r)) for r in pred] == [tuple(map(str, r)) for r in gold]
    return sorted(tuple(map(str, r)) for r in pred) == sorted(tuple(map(str, r)) for r in gold)

eq = {}
for q in sorted(set(CHANGED_PRIMARY) | set(CHANGED_DRIFT)):
    r = by_qid[q]
    o_rows, o_err = exec_rows(r["database"], r["gold_sql_original"])
    c_rows, c_err = exec_rows(r["database"], r["gold_sql_corrected"])
    if o_err or c_err:
        verdict = "execution_error"
    elif results_equal(o_rows, c_rows, r["gold_sql_corrected"]):
        verdict = "string_differs_results_EQUAL"
    else:
        verdict = "string_differs_results_DIFFER"
    eq[str(q)] = {"database": r["database"], "verdict": verdict,
                  "orig_error": o_err, "corr_error": c_err,
                  "in_primary_changed": q in set(CHANGED_PRIMARY),
                  "in_drift_changed": q in set(CHANGED_DRIFT)}
R["execution_equivalence_changed_tasks"] = eq

(HF / "mvr_analysis5.json").write_text(json.dumps(R, indent=1))
print(json.dumps({"overall_L1": R["overall_L1"],
                  "primary": {k: R["primary_corrected_subset"][k] for k in ("n", "changed_n", "unchanged_n")},
                  "drift": {k: R["drift_subset"][k] for k in ("n", "changed_n", "unchanged_n")},
                  "49v48": {k: R["n49_vs_48"][k] for k in ("sets_identical_all100", "stage1_corrected_primary_n", "replication_corrected_primary_n", "primary_without_corrected")},
                  "eq_summary": {v: sum(1 for e in eq.values() if e["verdict"] == v)
                                 for v in ("string_differs_results_DIFFER", "string_differs_results_EQUAL", "execution_error")}}, indent=1))
for name, blk in C.items():
    if "passk" in name:
        print(name, json.dumps(blk))
    else:
        print(f"{name}: full n={blk['subset_n']} diff={blk['full_corrected']['diff']} ci={blk['full_corrected']['ci95']} | "
              f"changed n={blk['changed_n']} diff={blk['changed_only']['diff']} ci={blk['changed_only']['ci95']} | "
              f"unchanged n={blk['unchanged_n']} diff={blk['unchanged_only']['diff']} ci={blk['unchanged_only']['ci95']}")
