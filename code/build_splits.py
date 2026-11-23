#!/usr/bin/env python3
"""Paper #1 — split construction (Protocol S6, sizes per Amendment A4).
Repeated-failure split: structural clustering within each database.
Features from gold SQL (construction metadata only; gold never enters prompts/episodes):
  table set (FROM/JOIN identifiers), skeleton token set (literals/numbers masked),
  question token set.
Distance(a,b) = 1 - [0.5*J(tables) + 0.3*J(skeleton) + 0.2*J(question)]  (same-DB pairs only)
Clusters = identical (db, table-set) signature groups with >=2 tasks.
Selection: greedy over clusters (largest first, DB-balanced), L1-preferred, excluding
dry-run tasks and slow-gold tasks. Each selected Session-2 task is paired with its
nearest distinct Session-1 partner in the same cluster. Seed-fixed random session order.
Outputs: splits_repeated.csv + distance stats for the near-duplicate threshold decision.
"""
import csv, json, re, random, itertools, collections, pathlib

HF = pathlib.Path(__file__).parent
random.seed(20261122)
man = list(csv.DictReader(open(HF / "manifest_v1.csv")))
by_qid = {int(r["source_task_id"]): r for r in man}

def tables_of(sql):
    s = sql.replace("`", " ").replace('"', " ")
    tabs = re.findall(r"(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.I)
    return frozenset(t.lower() for t in tabs)

def skeleton_tokens(sql):
    s = sql.lower()
    s = re.sub(r"'[^']*'", " ? ", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", " # ", s)
    return frozenset(re.findall(r"[a-z_][a-z0-9_]*|[*(),.=<>+/%-]", s))

def q_tokens(q):
    return frozenset(re.findall(r"[a-z0-9]+", q.lower()))

def jac(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))

feats = {}
for qid, r in by_qid.items():
    sql = r["gold_sql_original"]
    feats[qid] = (tables_of(sql), skeleton_tokens(sql), q_tokens(r["question"]))

def dist(a, b):
    ta, sa, qa = feats[a]
    tb, sb, qb = feats[b]
    return 1 - (0.5 * jac(ta, tb) + 0.3 * jac(sa, sb) + 0.2 * jac(qa, qb))

eligible = {qid for qid, r in by_qid.items()
            if r["split"] != "dry-run" and r["slow_gold_query"] != "yes"}
clusters = collections.defaultdict(list)
for qid in eligible:
    r = by_qid[qid]
    clusters[(r["database"], feats[qid][0])].append(qid)
clusters = {k: v for k, v in clusters.items() if len(v) >= 2}
print(f"eligible tasks: {len(eligible)}; multi-task (db,table-set) clusters: {len(clusters)}; "
      f"tasks in clusters: {sum(len(v) for v in clusters.values())}")

# greedy selection: round-robin over databases, largest clusters first, L1 first within cluster
by_db = collections.defaultdict(list)
for (db, sig), members in clusters.items():
    by_db[db].append((sig, members))
for db in by_db:
    by_db[db].sort(key=lambda x: -len(x[1]))

selected = []          # (s2_qid, s1_qid, cluster_key, distance)
used = set()
dbs = sorted(by_db)
TARGET = 100
progress = True
while len(selected) < TARGET and progress:
    progress = False
    for db in dbs:
        if len(selected) >= TARGET:
            break
        for sig, members in by_db[db]:
            free = [m for m in members if m not in used]
            if len(free) < 2:
                continue
            free.sort(key=lambda m: (by_qid[m]["label_status"] != "L1", m))
            s2 = free[0]
            partner, dmin = None, 2.0
            for cand in free[1:]:
                d = dist(s2, cand)
                if d < dmin:
                    partner, dmin = cand, d
            if partner is None:
                continue
            if random.random() < 0.5:
                s2, partner = partner, s2
            selected.append((s2, partner, (db, sig), dmin))
            used.add(s2); used.add(partner)
            progress = True
            break  # one pair per DB per round -> balance

print(f"selected pairs: {len(selected)} (Session-2 tasks: {len(selected)})")
ds = sorted(d for *_x, d in selected)
if ds:
    import statistics
    print(f"pair distance: min={ds[0]:.3f} p5={ds[len(ds)//20]:.3f} p25={ds[len(ds)//4]:.3f} "
          f"median={statistics.median(ds):.3f} p75={ds[3*len(ds)//4]:.3f} max={ds[-1]:.3f}")
    print("distance histogram:", collections.Counter(round(d, 1) for d in ds))
print("pairs per DB:", collections.Counter(by_qid[s2]["database"] for s2, *_ in selected))
print("L1 share of Session-2 tasks:", sum(1 for s2, *_ in selected if by_qid[s2]["label_status"] == "L1") / max(1, len(selected)))

with open(HF / "splits_repeated.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cluster_id", "database", "session2_qid", "session1_qid", "pair_distance",
                "s2_label_status", "s1_label_status"])
    for i, (s2, s1, (db, sig), d) in enumerate(selected):
        w.writerow([f"R{i:03d}", db, s2, s1, f"{d:.4f}", by_qid[s2]["label_status"], by_qid[s1]["label_status"]])
print("wrote splits_repeated.csv")
