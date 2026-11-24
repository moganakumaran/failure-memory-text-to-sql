#!/usr/bin/env python3
"""BIRD-FanOut cross-check (morning brief 2026-11-24, Paper #1 angle).

Question: how much does Mohan's 49-task corrected (L1) subset overlap
Mahran's public BIRD-FanOut lists, i.e. is the label defect in the 49
annotation error, fan-out error, or both?

Sources (all local / already read in the browser):
- 49 qids: b02_subset_results.json (corrected_subset_qids), derived from
  manifest_v2.csv (dev_20240627, 1,534 tasks) + splits_repeated.csv.
- FanOut June 2024 pilot: bird_fanout_june2024_subset.jsonl (93 lines,
  same dev release as Mohan's substrate).
- FanOut dev 2025-11-06: bird_fanout_dev20251106_subset.jsonl (127 lines,
  cleaned release; 102 harness questions after gold review).

Alignment gate: for EVERY FanOut record, the manifest row with the same
source_task_id must agree on database and question text (whitespace
normalised). If any mismatch, the qid join is invalid and the script
aborts. No model calls; pure join of stored data.
"""
import csv, json, pathlib, re

HF = pathlib.Path(__file__).parent

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())

corr49 = json.loads((HF / "b02_subset_results.json").read_text())["corrected_subset_qids"]
assert len(corr49) == 49, len(corr49)
CORR49 = set(corr49)

man = {int(r["source_task_id"]): r for r in csv.DictReader(open(HF / "manifest_v2.csv"))}
assert len(man) == 1534

def load(fn):
    return [json.loads(l) for l in open(HF / fn) if l.strip()]

def check(fn):
    """Alignment gate: db_id must match for every record (hard fail
    otherwise). Question text must match, except for release rewordings:
    the 2025-11-06 cleaned release reworded 11 questions on the same
    topic in the same db (6 carry old_question; the other 5 inspected
    manually — same db/topic, edited wording, e.g. q1173 differs by one
    comma). Those are recorded, not silently accepted."""
    recs = load(fn)
    mismatches = []
    reworded = []
    for r in recs:
        qid = int(r["id"])
        m = man.get(qid)
        if m is None:
            mismatches.append((qid, "no manifest row"))
            continue
        if m["database"] != r["db_id"]:
            mismatches.append((qid, f"db {m['database']} != {r['db_id']}"))
        elif norm(m["question"]) != norm(r["question"]):
            reworded.append(qid)
    return recs, mismatches, reworded

out = {"corrected_subset_n": 49, "lists": {}}
for name, fn in [("june2024_pilot", "bird_fanout_june2024_subset.jsonl"),
                 ("dev20251106", "bird_fanout_dev20251106_subset.jsonl")]:
    recs, mism, reworded = check(fn)
    assert not mism, (name, mism[:5])
    cats = {}
    for r in recs:
        cats.setdefault(r["category"], []).append(int(r["id"]))
    overlap = sorted(CORR49 & {int(r["id"]) for r in recs})
    by_cat = {}
    for r in recs:
        if int(r["id"]) in CORR49:
            by_cat.setdefault(r["category"], []).append({
                "qid": int(r["id"]), "db_id": r["db_id"],
                "question": r["question"][:120],
                "has_corrected_sql": bool(r.get("corrected_sql")),
            })
    out["lists"][name] = {
        "n_records": len(recs),
        "by_category": {k: len(v) for k, v in sorted(cats.items())},
        "overlap_with_49_n": len(overlap),
        "overlap_qids": overlap,
        "overlap_by_category": {k: v for k, v in sorted(by_cat.items())},
        "overlap_share_of_49_pct": round(100 * len(overlap) / 49, 1),
        "overlap_share_of_list_pct": round(100 * len(overlap) / len(recs), 1),
        "reworded_qids_in_this_list": sorted(reworded),
        "overlap_qids_that_are_reworded": sorted(set(overlap) & set(reworded)),
    }

# Context: FanOut overlap with the full 97 primary tasks (Session-2 minus recall controls)
pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
s2 = {int(p["session2_qid"]) for p in pairs}
primary = s2 - {850, 1326, 1479}
assert len(primary) == 97, len(primary)
out["primary_n"] = 97
for name, fn in [("june2024_pilot", "bird_fanout_june2024_subset.jsonl"),
                 ("dev20251106", "bird_fanout_dev20251106_subset.jsonl")]:
    ids = {int(json.loads(l)["id"]) for l in open(HF / fn) if l.strip()}
    out["lists"][name]["overlap_with_primary97_n"] = len(primary & ids)
    out["lists"][name]["overlap_with_primary97_qids"] = sorted(primary & ids)

(HF / "fanout_crosscheck_results.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
