#!/usr/bin/env python3
"""MVR Analysis 6 — drift-adjusted corrected golds + re-scoring of stored drift
trajectories (Paper #1 PVLDB minimum viable revision, panel fix item 6 / W7).

Problem: the paper's corrected-label drift view executes Jin et al.'s corrected
SQL — written against the ORIGINAL database — on the DRIFTED database
(pilot.py: corr_sql executed on db_path, which is the drifted DB in the drift
phase). For schema_column_rename tasks that gold does not even execute
(no such column), so every corrected-label pass is False by construction;
for value-recode / category-merge tasks it filters on pre-drift literals.

Fix (scoring only; NO model calls): apply to each task's corrected SQL the
SAME drift-operator transform that build_drift.py applied to the original
gold to produce drifted_gold_sql, mirroring build_drift.py exactly:

  schema_column_rename : re.sub(rf"`{c}`|\\b{c}\\b", f"`{new}`", gold)
                         (here: word-boundary replace of the old column name
                         outside single-quoted string literals; validated by
                         requiring the adjusted result on the drifted DB to
                         equal the corrected result on the original DB —
                         the same result-identical check build_drift.py used)
  data_value_recode    : gold.replace(f"'{v}'", f"'{v}_X'")
  category_merge       : gold.replace(f"'{gone}'", f"'{keep}'")
  data_unit_change     : gold unchanged (build_drift.py: drifted_gold = gold)
  schema_type_change   : gold unchanged
  temporal_grain_change: gold unchanged
  null_semantics_change: gold unchanged

For the four identity operators, and for recode/merge tasks whose corrected
SQL does not contain the drifted literal, the adjusted SQL text equals the
corrected SQL, and the expected result set is obtained — exactly as in the
original-label view — by executing it on the drifted database. For identity
operators the new pass is therefore definitionally identical to the stored
old pass; stored flags are carried over for those tasks (avoids re-execution
timeout noise) and a re-execution agreement check is reported instead.

Transform parameters are parsed from drift_spec.csv's `detail` column, which
records the exact table/column/value the original build used.

Estimators mirror analysis_a14.py exactly (per-task run-mean pass@1, paired
task-level bootstrap, 10000 resamples, seed 20261122, percentile CI at
indices 250/9750). Scoring mirrors pilot_lib.results_equal (multiset
comparison, order-sensitive when the gold SQL has ORDER BY) and
pilot_lib.exec_sql (read-only; gold executions use a 20s limit and
predicted-SQL executions 15s, vs pilot's 10s — noted where it binds; a
larger page cache is set for speed only, which does not change results).

Outputs:
  mvr_drift_adjusted_corrected_golds.jsonl
  mvr_analysis6.json
"""
import csv, json, glob, random, re, sys, pathlib
from collections import defaultdict

HF = pathlib.Path(__file__).parent
sys.path.insert(0, str(HF))
import pilot_lib as L

random.seed(20261122)
GOLD_LIMIT = 20.0   # pilot used 10s; 20s is generous while still aborting
PRED_LIMIT = 15.0   # pathological golds (q116's corrected SQL reads >50 GB)

import sqlite3, time

def exec_sql_fast(db_path, sql, limit=10.0):
    """Semantics identical to pilot_lib.exec_sql (read-only URI,
    fetchmany(100000), progress-handler abort after `limit` s, rows-or-None);
    only the page cache / temp store are enlarged so slow-but-finite queries
    are not disk-thrashed on this shared VM."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-65536")
    con.execute("PRAGMA temp_store=MEMORY")
    deadline = time.time() + limit
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 1000)
    try:
        rows = con.execute(sql).fetchmany(100000)
        return rows, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        con.close()

DBROOT = HF / "datasets/bird/dev_20240627/dev_databases/dev_databases"

man = {int(r["source_task_id"]): r for r in csv.DictReader(open(HF / "manifest_v2.csv"))}
spec_rows = list(csv.DictReader(open(HF / "drift_spec.csv")))
spec = {int(r["qid"]): r for r in spec_rows}
SILENT = {q for q, r in spec.items() if r["drift_type"] == "silent"}
IDENTITY_OPS = {"data_unit_change", "schema_type_change",
                "temporal_grain_change", "null_semantics_change"}

# ---------------------------------------------------------------- transforms
def parse_detail(op, detail):
    if op == "schema_column_rename":
        m = re.match(r"column (.+)\.(.+) renamed to (.+)$", detail)
        return {"table": m.group(1), "old": m.group(2), "new": m.group(3)}
    if op == "data_value_recode":
        left, right = detail.split("' recoded to '")
        v = left.split(": '", 1)[1]
        newv = right[:-1] if right.endswith("'") else right
        return {"old_literal": v, "new_literal": newv}
    if op == "category_merge":
        left, right = detail.split("' merged into '")
        gone = left.split(": '", 1)[1]
        keep = right[:-1] if right.endswith("'") else right
        return {"old_literal": gone, "new_literal": keep}
    return {}

LIT_RE = re.compile(r"'(?:[^']|'')*'")

def replace_outside_literals(sql, old, new):
    """Word-boundary replace of identifier `old` -> `new`, skipping
    single-quoted string literals. Returns (new_sql, n_replacements)."""
    out, n, pos = [], 0, 0
    pat = re.compile(rf"\b{re.escape(old)}\b")
    for m in LIT_RE.finditer(sql):
        seg = sql[pos:m.start()]
        seg2, k = pat.subn(new, seg)
        n += k
        out.append(seg2); out.append(m.group(0)); pos = m.end()
    seg = sql[pos:]
    seg2, k = pat.subn(new, seg)
    n += k
    out.append(seg2)
    return "".join(out), n

def rename_alias_fallback(sql, table, old, new):
    """Fallback: replace only occurrences qualified by the renamed table's
    name/aliases, plus quoted unqualified occurrences."""
    quals = {table}
    for m in re.finditer(rf"(?:FROM|JOIN)\s+`?{re.escape(table)}`?\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
                         sql, re.I):
        quals.add(m.group(1))
    out, n = sql, 0
    for q in quals:
        for pat, rep in [(rf"(\b{re.escape(q)}\s*\.\s*`){re.escape(old)}(`)", rf"\g<1>{new}\g<2>"),
                         (rf'(\b{re.escape(q)}\s*\.\s*"){re.escape(old)}(")', rf"\g<1>{new}\g<2>"),
                         (rf"(\b{re.escape(q)}\s*\.\s*){re.escape(old)}\b", rf"\g<1>{new}")]:
            out, k = re.subn(pat, rep, out)
            n += k
    out2, k = replace_outside_literals(out, f"`{old}`", f"`{new}`")
    # replace_outside_literals does word-boundary on the given token; the
    # backticked form is handled by counting raw occurrences instead:
    n += k
    return out2, n

def apply_transform(qid):
    """Returns dict with adjusted SQL + status/note. Mirrors build_drift.py."""
    s = spec[qid]; op = s["operator"]
    corr = man[qid]["gold_sql_corrected"]
    p = parse_detail(op, s["detail"])
    if op in IDENTITY_OPS:
        return {"adjusted_sql": corr, "status": "identity",
                "note": f"build_drift.py leaves gold SQL unchanged for {op}; "
                        f"expected result comes from executing on the drifted DB",
                "params": p}
    if op == "schema_column_rename":
        adj, n = replace_outside_literals(corr, p["old"], p["new"])
        return {"adjusted_sql": adj, "status": "applied" if n else "failed-no-occurrence",
                "note": f"column {p['table']}.{p['old']} -> {p['new']}: {n} occurrence(s) replaced "
                        f"(word-boundary, outside string literals)",
                "params": p, "n_replacements": n}
    if op in ("data_value_recode", "category_merge"):
        old_tok = f"'{p['old_literal']}'"
        new_tok = f"'{p['new_literal']}'"
        n = corr.count(old_tok)
        if n:
            return {"adjusted_sql": corr.replace(old_tok, new_tok), "status": "applied",
                    "note": f"literal {old_tok} -> {new_tok}: {n} occurrence(s) replaced "
                            f"(str.replace, as in build_drift.py)",
                    "params": p, "n_replacements": n}
        esc_old = "'" + p["old_literal"].replace("'", "''") + "'"
        esc_new = "'" + p["new_literal"].replace("'", "''") + "'"
        n2 = corr.count(esc_old)
        if n2:
            return {"adjusted_sql": corr.replace(esc_old, esc_new), "status": "applied-escaped",
                    "note": f"literal (''-escaped form) replaced: {n2} occurrence(s)",
                    "params": p, "n_replacements": n2}
        return {"adjusted_sql": corr, "status": "noop-literal-absent",
                "note": f"corrected SQL does not contain literal {old_tok}; adjusted SQL = "
                        f"corrected SQL (expected result still obtained on the drifted DB, "
                        f"mirroring build_drift.py, whose drifted gold is likewise unchanged "
                        f"for this task)",
                "params": p, "n_replacements": 0}
    return {"adjusted_sql": corr, "status": "failed-unknown-operator",
            "note": op, "params": p}

# ---------------------------------------------------------------- gold exec
gold_records = {}
for qid in sorted(spec):
    s = spec[qid]; op = s["operator"]
    db = s["database"]
    drift_db = pathlib.Path(s["drifted_db_path"])
    orig_db = DBROOT / db / f"{db}.sqlite"
    corr = man[qid]["gold_sql_corrected"]
    tr = apply_transform(qid)
    adj = tr["adjusted_sql"]
    print(f"[gold] q{qid} {op}", flush=True)
    adj_rows, adj_err = exec_sql_fast(drift_db, adj, limit=GOLD_LIMIT)
    if adj_err and "interrupted" in adj_err:
        # one retry with a long limit: a slow-but-finite gold must not be
        # confused with a failed gold (disk contention on this shared VM
        # inflates runtimes; q116's gold reads tens of GB uncached)
        adj_rows, adj_err = exec_sql_fast(drift_db, adj, limit=90.0)
    if adj == corr:
        old_rows, old_err = adj_rows, adj_err
    else:
        old_rows, old_err = exec_sql_fast(drift_db, corr, limit=GOLD_LIMIT)
    orig_rows, orig_err = exec_sql_fast(orig_db, corr, limit=GOLD_LIMIT)
    # rename validation: adjusted-on-drifted must reproduce corrected-on-original
    validation = None
    if op == "schema_column_rename":
        if adj_err:
            validation = f"FAIL: adjusted gold does not execute on drifted DB: {adj_err}"
        elif orig_err:
            validation = f"UNCHECKABLE: corrected gold does not execute on original DB: {orig_err}"
        elif L.results_equal(adj_rows, orig_rows, adj):
            validation = "PASS: adjusted result on drifted DB == corrected result on original DB"
        else:
            validation = "FAIL: adjusted result on drifted DB != corrected result on original DB"
        if validation.startswith("FAIL"):
            # Fallbacks, in order: (a) alias-restricted replacement (only
            # occurrences qualified by the renamed table), (b) identity —
            # the corrected SQL may not reference the renamed column at all
            # while referencing a same-named column of another table (q25:
            # frpm.CDSCode renamed, but the corrected SQL uses
            # schools.CDSCode via alias sc and never touches frpm).
            fb, nf = rename_alias_fallback(corr, tr["params"]["table"],
                                           tr["params"]["old"], tr["params"]["new"])
            candidates = [("alias-restricted fallback", fb, nf),
                          ("identity (corrected SQL does not use the renamed column)", corr, 0)]
            for cand_name, cand_sql, cand_n in candidates:
                if cand_sql == adj:
                    continue
                fb_rows, fb_err = exec_sql_fast(drift_db, cand_sql, limit=GOLD_LIMIT)
                if fb_err and "interrupted" in fb_err:
                    fb_rows, fb_err = exec_sql_fast(drift_db, cand_sql, limit=90.0)
                if not fb_err and not orig_err and L.results_equal(fb_rows, orig_rows, cand_sql):
                    tr = dict(tr); tr["adjusted_sql"] = cand_sql
                    tr["note"] += (f" | global replace failed validation ({validation}); "
                                   f"{cand_name} used ({cand_n} replacements)")
                    tr["status"] = "applied-fallback"
                    adj, adj_rows, adj_err = cand_sql, fb_rows, fb_err
                    validation = (f"PASS ({cand_name}): adjusted result on drifted DB "
                                  f"== corrected result on original DB")
                    break
    if old_err and adj_err:
        changed = None; change_reason = "both old and adjusted gold fail to execute on drifted DB"
    elif old_err:
        changed = True; change_reason = f"old (unadjusted) gold fails on drifted DB ({old_err}); adjusted gold executes"
    elif adj_err:
        changed = True; change_reason = f"adjusted gold fails on drifted DB ({adj_err}); old gold executed"
    else:
        changed = not L.results_equal(adj_rows, old_rows, adj)
        change_reason = ("expected result set differs between adjusted and unadjusted gold "
                         "on the drifted DB" if changed else
                         "expected result set identical under old and new gold on the drifted DB")
    gold_records[qid] = {
        "qid": qid, "database": db, "operator": op, "drift_type": s["drift_type"],
        "detail": s["detail"],
        "original_corrected_sql": corr,
        "adjusted_sql": adj,
        "transform_status": tr["status"], "transform_note": tr["note"],
        "rename_validation": validation,
        "exec_status_adjusted_on_drifted": "ok" if adj_err is None else f"error: {adj_err}",
        "exec_error_adjusted": adj_err,
        "n_rows_adjusted": (len(adj_rows) if adj_rows is not None else None),
        "exec_status_oldgold_on_drifted": "ok" if old_err is None else f"error: {old_err}",
        "exec_status_corrected_on_original": "ok" if orig_err is None else f"error: {orig_err}",
        "expected_result_changed": changed, "expected_change_reason": change_reason,
        "_adj_rows": adj_rows, "_old_rows": old_rows,
    }

# ---------------------------------------------------------------- traces
def load(pattern, phase=None, arm=None):
    rows = []
    for f in sorted(glob.glob(str(HF / pattern))):
        if "starved" in f or "smoke" in f:
            continue
        for l in open(f):
            t = json.loads(l)
            if phase and t.get("phase") != phase: continue
            if arm and t.get("arm") != arm: continue
            rows.append(t)
    return rows

drift_traces = load("traces_stage2_drift_run*.jsonl", phase="drift")
undrift_traces = load("traces_fix_ctrl_run*.jsonl", phase="undrifted", arm="A0")
assert len(drift_traces) == 720, len(drift_traces)
assert len(undrift_traces) == 240, len(undrift_traces)

# re-score drift traces under the NEW corrected view
rescore_old_agree = {"agree": 0, "disagree": 0, "examples": []}
identity_recheck = {"agree": 0, "disagree": 0, "skipped_gold_unexecutable": 0}
for t in drift_traces:
    qid = t["qid"]; op = spec[qid]["operator"]
    gr = gold_records[qid]
    t["pass_corrected_old"] = t.get("pass_corrected")
    if op in IDENTITY_OPS:
        t["pass_corrected_new"] = t.get("pass_corrected")  # definitional identity
        # informational re-execution agreement check
        if gr["_adj_rows"] is not None:
            pred_rows, pred_err = exec_sql_fast(pathlib.Path(spec[qid]["drifted_db_path"]),
                                                t["answer_sql"], limit=PRED_LIMIT)
            chk = L.results_equal(pred_rows, gr["_adj_rows"], gr["adjusted_sql"])
            if chk == bool(t.get("pass_corrected")):
                identity_recheck["agree"] += 1
            else:
                identity_recheck["disagree"] += 1
        else:
            identity_recheck["skipped_gold_unexecutable"] += 1
        continue
    # transformed operators: full re-score against adjusted gold
    if gr["_adj_rows"] is None:
        t["pass_corrected_new"] = None  # adjusted gold unexecutable: excluded, logged
        continue
    pred_rows, pred_err = exec_sql_fast(pathlib.Path(spec[qid]["drifted_db_path"]),
                                        t["answer_sql"], limit=PRED_LIMIT)
    t["pass_corrected_new"] = L.results_equal(pred_rows, gr["_adj_rows"], gr["adjusted_sql"])
    # validation: re-score under OLD gold and compare with the stored old flag
    if gr["_old_rows"] is not None:
        old_chk = L.results_equal(pred_rows, gr["_old_rows"], man[qid]["gold_sql_corrected"])
    else:
        old_chk = False  # pilot: gold rows None -> results_equal False
    if old_chk == bool(t.get("pass_corrected")):
        rescore_old_agree["agree"] += 1
    else:
        rescore_old_agree["disagree"] += 1
        if len(rescore_old_agree["examples"]) < 10:
            rescore_old_agree["examples"].append(
                {"qid": qid, "arm": t["arm"], "run_id": t["run_id"],
                 "stored_old": t.get("pass_corrected"), "rescored_old": old_chk})

for t in undrift_traces:
    t["pass_corrected_old"] = t.get("pass_corrected")
    t["pass_corrected_new"] = t.get("pass_corrected")  # undrifted corrected scoring was already valid

# ---------------------------------------------------------------- estimators (mirror analysis_a14.py)
def per_task(rows, label, tasks=None):
    d = defaultdict(list)
    for t in rows:
        if tasks is not None and t["qid"] not in tasks: continue
        v = t.get(label)
        if v is None: continue
        d[t["qid"]].append(1 if v else 0)
    return {q: sum(v) / len(v) for q, v in d.items()}

def paired_diff(rows_a, rows_b, label, tasks=None):
    da, db = per_task(rows_a, label, tasks), per_task(rows_b, label, tasks)
    common = sorted(set(da) & set(db))
    diffs = [db[q] - da[q] for q in common]
    point = sum(diffs) / len(diffs)
    boots = []
    for _ in range(10000):
        s = [diffs[random.randrange(len(diffs))] for _ in diffs]
        boots.append(sum(s) / len(s))
    boots.sort()
    return {"tasks": len(common), "diff": round(point, 4),
            "ci95": [round(boots[250], 4), round(boots[9750], 4)]}

def level(rows, label, tasks=None):
    pt = per_task(rows, label, tasks)
    return {"tasks": len(pt), "pass1": round(sum(pt.values()) / len(pt), 4)}

A0d = [t for t in drift_traces if t["arm"] == "A0"]
A1d = [t for t in drift_traces if t["arm"] == "A1"]
A4d = [t for t in drift_traces if t["arm"] == "A4"]

R = {}
R["levels"] = {
    "undrifted_A0_corrected_old": level(undrift_traces, "pass_corrected_old"),
    "undrifted_A0_corrected_new": level(undrift_traces, "pass_corrected_new"),
    "drifted_A0_corrected_old": level(A0d, "pass_corrected_old"),
    "drifted_A0_corrected_new": level(A0d, "pass_corrected_new"),
    "drifted_A1_corrected_old": level(A1d, "pass_corrected_old"),
    "drifted_A1_corrected_new": level(A1d, "pass_corrected_new"),
    "drifted_A4_corrected_old": level(A4d, "pass_corrected_old"),
    "drifted_A4_corrected_new": level(A4d, "pass_corrected_new"),
    "undrifted_A0_original": level(undrift_traces, "pass_original"),
    "drifted_A0_original": level(A0d, "pass_original"),
}
R["contrasts"] = {
    "paired_drift_effect_A0_corrected_old": paired_diff(undrift_traces, A0d, "pass_corrected_old"),
    "paired_drift_effect_A0_corrected_new": paired_diff(undrift_traces, A0d, "pass_corrected_new"),
    "paired_drift_effect_A0_original_sanity": paired_diff(undrift_traces, A0d, "pass_original"),
    "A1_minus_A0_drift_corrected_old": paired_diff(A0d, A1d, "pass_corrected_old"),
    "A1_minus_A0_drift_corrected_new": paired_diff(A0d, A1d, "pass_corrected_new"),
    "A4_minus_A0_drift_corrected_old": paired_diff(A0d, A4d, "pass_corrected_old"),
    "A4_minus_A0_drift_corrected_new": paired_diff(A0d, A4d, "pass_corrected_new"),
    "A4_minus_A1_drift_corrected_old": paired_diff(A1d, A4d, "pass_corrected_old"),
    "A4_minus_A1_drift_corrected_new": paired_diff(A1d, A4d, "pass_corrected_new"),
    "A1_minus_A0_drift_original_sanity": paired_diff(A0d, A1d, "pass_original"),
    "A4_minus_A0_drift_original_sanity": paired_diff(A0d, A4d, "pass_original"),
    "A4_minus_A1_drift_original_sanity": paired_diff(A1d, A4d, "pass_original"),
    # silent-drift subsets (33 tasks)
    "paired_drift_effect_A0_corrected_old_silent": paired_diff(undrift_traces, A0d, "pass_corrected_old", SILENT),
    "paired_drift_effect_A0_corrected_new_silent": paired_diff(undrift_traces, A0d, "pass_corrected_new", SILENT),
    "A4_minus_A0_drift_corrected_old_silent": paired_diff(A0d, A4d, "pass_corrected_old", SILENT),
    "A4_minus_A0_drift_corrected_new_silent": paired_diff(A0d, A4d, "pass_corrected_new", SILENT),
    "A1_minus_A0_drift_corrected_old_silent": paired_diff(A0d, A1d, "pass_corrected_old", SILENT),
    "A1_minus_A0_drift_corrected_new_silent": paired_diff(A0d, A1d, "pass_corrected_new", SILENT),
    "A4_minus_A0_drift_original_silent_sanity": paired_diff(A0d, A4d, "pass_original", SILENT),
}

# per-operator summaries
per_op = {}
for op in sorted({r["operator"] for r in spec.values()}):
    qs = [q for q, r in spec.items() if r["operator"] == op]
    per_op[op] = {
        "tasks": len(qs),
        "transform_applied": sum(1 for q in qs if gold_records[q]["transform_status"].startswith("applied")),
        "transform_identity": sum(1 for q in qs if gold_records[q]["transform_status"] == "identity"),
        "transform_noop_literal_absent": sum(1 for q in qs if gold_records[q]["transform_status"] == "noop-literal-absent"),
        "transform_failed": sum(1 for q in qs if gold_records[q]["transform_status"].startswith("failed")),
        "adjusted_gold_executes_on_drifted": sum(1 for q in qs if gold_records[q]["exec_error_adjusted"] is None),
        "adjusted_gold_exec_failures": [q for q in qs if gold_records[q]["exec_error_adjusted"] is not None],
        "old_gold_executes_on_drifted": sum(1 for q in qs if gold_records[q]["exec_status_oldgold_on_drifted"] == "ok"),
        "expected_result_changed_tasks": [q for q in qs if gold_records[q]["expected_result_changed"]],
        "rename_validation": {str(q): gold_records[q]["rename_validation"] for q in qs
                              if gold_records[q]["rename_validation"]},
    }
R["per_operator"] = per_op
R["validation"] = {"rescore_old_agreement_transformed_tasks": rescore_old_agree,
                   "identity_task_reexecution_agreement": identity_recheck}
R["failures"] = [
    {"qid": q, "operator": g["operator"], "transform_status": g["transform_status"],
     "transform_note": g["transform_note"], "rename_validation": g["rename_validation"],
     "exec_status_adjusted_on_drifted": g["exec_status_adjusted_on_drifted"],
     "exec_status_corrected_on_original": g["exec_status_corrected_on_original"]}
    for q, g in sorted(gold_records.items())
    if g["transform_status"].startswith("failed")
    or (g["rename_validation"] or "").startswith(("FAIL", "UNCHECKABLE"))
    or g["exec_error_adjusted"] is not None]
R["expected_result_changed_all"] = [q for q, g in sorted(gold_records.items())
                                    if g["expected_result_changed"]]
R["n_traces_rescored_new_none"] = sum(1 for t in drift_traces if t.get("pass_corrected_new") is None)

with open(HF / "mvr_drift_adjusted_corrected_golds.jsonl", "w") as f:
    for qid in sorted(gold_records):
        g = {k: v for k, v in gold_records[qid].items() if not k.startswith("_")}
        f.write(json.dumps(g) + "\n")
json.dump(R, open(HF / "mvr_analysis6.json", "w"), indent=1)
print(json.dumps(R, indent=1))
