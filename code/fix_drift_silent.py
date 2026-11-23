#!/usr/bin/env python3
"""Fix-up: raise the drift split's silent share to >=50% (Protocol S6).
For tasks currently assigned an OVERT operator, retry SILENT operators only
(reusing build_drift.try_build); on success replace the spec row and remove the
old overt variant directory. Targets silent >= 33/60 for margin.
Also deletes orphan variant directories not referenced by drift_spec.csv.
"""
import csv, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_drift_lib as bd

HF = pathlib.Path(__file__).parent
spec_path = HF / "drift_spec.csv"
rows = list(csv.DictReader(open(spec_path)))
man = {int(r["source_task_id"]): r for r in csv.DictReader(open(HF / "manifest_v1.csv"))}
SILENT_OPS = ["data_value_recode", "category_merge", "data_unit_change",
              "temporal_grain_change", "null_semantics_change"]

silent = sum(1 for r in rows if r["drift_type"] == "silent")
print(f"before: silent {silent}/60")
overt_rows = [r for r in rows if r["drift_type"] == "overt"]
# prefer converting type_change first, then renames (keep some overt controls)
overt_rows.sort(key=lambda r: 0 if r["operator"] == "schema_type_change" else 1)
for r in overt_rows:
    if silent >= 33:
        break
    task = man[int(r["qid"])]
    for op in SILENT_OPS:
        try:
            built = bd.try_build(task, op)
        except Exception as e:
            print(f"q{r['qid']} {op}: {type(e).__name__} {e}")
            built = None
        if built:
            old_dir = pathlib.Path(r["drifted_db_path"]).parent
            r.update({"operator": op, "drift_type": "silent",
                      "substituted_for": r["operator"] + " (silent-share fix-up)",
                      "detail": built["detail"], "verification": built["check"],
                      "drifted_gold_sql": built["drifted_gold"],
                      "drifted_db_path": str(bd.OUTROOT / f"{r['qid']}_{op}" /
                                             f"{r['database']}.sqlite")})
            if old_dir.exists():
                shutil.rmtree(old_dir)
            silent += 1
            print(f"q{r['qid']}: converted to {op} (silent now {silent})")
            break

with open(spec_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["qid", "database", "operator", "drift_type",
                                      "substituted_for", "label_status", "detail",
                                      "verification", "drifted_db_path", "drifted_gold_sql"])
    w.writeheader(); w.writerows(rows)
print(f"after: silent {sum(1 for r in rows if r['drift_type']=='silent')}/60; "
      f"operators: { {op: sum(1 for r in rows if r['operator']==op) for op in sorted(set(r['operator'] for r in rows))} }")

keep = {pathlib.Path(r["drifted_db_path"]).parent.name for r in rows}
removed = 0
for d in bd.OUTROOT.iterdir():
    if d.is_dir() and d.name not in keep:
        shutil.rmtree(d); removed += 1
print(f"orphan dirs removed: {removed}; dirs remaining: {len(list(bd.OUTROOT.iterdir()))}")
