#!/usr/bin/env python3
"""Build Paper #1 task manifest from BIRD Dev + Jin-repo Arcwise corrected labels.
Data files only; no external code is executed. Rules: Substrate Specification v2."""
import json, csv, re, random, hashlib, collections, pathlib

BASE = pathlib.Path(__file__).resolve().parent  # project root (see README: Layout)
BIRD = BASE / "hidden_files/datasets/bird/dev_20240627/dev.json"
ARC = BASE / "hidden_files/datasets/jin_corrected/text_to_sql_benchmarks/data/arcwise_plat_full_with_diff.json"
OUT = BASE / "hidden_files/manifest_v1.csv"
SEED = 20261122
SLOW = {101, 104, 341, 342, 344, 345, 518, 561, 562, 563, 701}  # gold SQL >10s in execution sweep 2026-11-22

bird = json.load(open(BIRD))
arc = {str(a["question_id"]): a for a in json.load(open(ARC))}

def proxies(sql):
    joins = len(re.findall(r"\bJOIN\b", sql, re.I))
    tables = set(t.strip('`"[]').lower() for t in re.findall(r"(?:FROM|JOIN)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)", sql, re.I))
    return len(sql), joins, len(tables)

rows = []
for x in bird:
    qid = str(x["question_id"])
    a = arc.get(qid)
    if a is not None:
        status = "L1"
        corrected = a["SQL"]
    else:
        status = "L2"
        corrected = ""
    sql_len, joins, tables = proxies(x["SQL"])
    rows.append({
        "task_id": f"bird-{qid}",
        "source": "BIRD Dev dev_20240627",
        "source_task_id": qid,
        "database": x["db_id"],
        "question": x["question"],
        "gold_sql_original": x["SQL"],
        "gold_sql_corrected": corrected,
        "label_status": status,
        "difficulty_given": x.get("difficulty", ""),
        "sql_len_chars": sql_len,
        "join_count": joins,
        "table_count": tables,
        "slow_gold_query": "yes" if x["question_id"] in SLOW else "no",
        "split": "unassigned",
        "cluster_id": "",
        "session": "",
        "drift_operator": "",
        "drift_type": "none",
        "exclusion_reason": "",
    })

# Dry-run sample: 1 task per database (11 DBs), seeded, per Substrate Spec s4 rule 4
rng = random.Random(SEED)
by_db = collections.defaultdict(list)
for r in rows:
    by_db[r["database"]].append(r)
dry_ids = []
for db in sorted(by_db):
    pick = rng.choice(sorted(by_db[db], key=lambda r: int(r["source_task_id"])))
    pick["split"] = "dry-run"
    dry_ids.append(pick["source_task_id"])

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

h = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
counts = collections.Counter(r["label_status"] for r in rows)
print("manifest rows:", len(rows))
print("label status:", dict(counts))
print("dry-run seed:", SEED, "task ids:", dry_ids)
print("manifest sha256:", h)
print("manifest path:", OUT)
