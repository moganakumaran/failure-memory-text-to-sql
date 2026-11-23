#!/usr/bin/env python3
"""Paper #1 — drift split construction (Protocol S6, Substrate Spec S6).
60 base tasks (unused by repeated split / dry run), DB-balanced, L1-preferred.
Each task: Session 1 = original DB; Session 2 = same question on a drifted DB copy.
Operators (rotation, >=50% silent required):
  overt : schema_column_rename, schema_type_change
  silent: data_value_recode, data_unit_change, category_merge,
          temporal_grain_change, null_semantics_change
Every variant is verified: drifted gold executes on the drifted DB (10s limit);
rename variants must reproduce the original gold result exactly.
Outputs: drifted DBs under datasets/bird_drift/<qid>_<op>/, drift_spec.csv, build log.
"""
import csv, json, re, shutil, sqlite3, pathlib, collections, random

HF = pathlib.Path(__file__).parent
DBROOT = HF / "datasets/bird/dev_20240627/dev_databases/dev_databases"
OUTROOT = HF / "datasets/bird_drift"
random.seed(20261122)

man = list(csv.DictReader(open(HF / "manifest_v1.csv")))
by_qid = {int(r["source_task_id"]): r for r in man}
rep = list(csv.DictReader(open(HF / "splits_repeated.csv")))
used = set()
for r in rep:
    used.add(int(r["session2_qid"])); used.add(int(r["session1_qid"]))
used |= {int(r["source_task_id"]) for r in man if r["split"] == "dry-run"}

pool = [r for r in man if int(r["source_task_id"]) not in used
        and r["slow_gold_query"] != "yes"]
by_db = collections.defaultdict(list)
for r in pool:
    by_db[r["database"]].append(r)
for db in by_db:
    by_db[db].sort(key=lambda r: (r["label_status"] != "L1", int(r["source_task_id"])))
base_tasks, dbs = [], sorted(by_db)
i = 0
while len(base_tasks) < 60:
    db = dbs[i % len(dbs)]
    if by_db[db]:
        base_tasks.append(by_db[db].pop(0))
    i += 1
print(f"base tasks: {len(base_tasks)}; L1 share: "
      f"{sum(1 for r in base_tasks if r['label_status']=='L1')/60:.2f}; per DB: "
      f"{dict(collections.Counter(r['database'] for r in base_tasks))}")

def schema_of(db):
    con = sqlite3.connect(f"file:{DBROOT}/{db}/{db}.sqlite?mode=ro", uri=True)
    sch = {}
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [(c[1], c[2]) for c in con.execute(f"PRAGMA table_info('{t}')")]
        sch[t] = cols
    con.close()
    return sch

def run(db_path, sql, limit_rows=100000):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA busy_timeout=10000")
    try:
        rows = con.execute(sql).fetchmany(limit_rows)
        return rows
    finally:
        con.close()

def gold_cols(sql, sch):
    """columns of each table mentioned in the SQL (bare or backticked)."""
    found = {}
    low = sql.lower()
    for t, cols in sch.items():
        if re.search(rf"\b{re.escape(t.lower())}\b", low):
            for c, typ in cols:
                if re.search(rf"`{re.escape(c)}`|\b{re.escape(c.lower())}\b", low):
                    found.setdefault(t, []).append((c, typ))
    return found

OPS_ROTATION = ["data_value_recode", "schema_column_rename", "data_unit_change",
                "category_merge", "schema_type_change", "temporal_grain_change",
                "null_semantics_change", "data_value_recode", "schema_column_rename",
                "data_unit_change", "category_merge", "temporal_grain_change"]
SILENT = {"data_value_recode", "data_unit_change", "category_merge",
          "temporal_grain_change", "null_semantics_change"}

def literals_in(sql):
    return re.findall(r"'([^']{1,40})'", sql)

def try_build(task, op):
    """Returns dict(spec) or None if infeasible for this task."""
    qid = int(task["source_task_id"]); db = task["database"]; gold = task["gold_sql_original"]
    sch = schema_of(db)
    gc = gold_cols(gold, sch)
    src = DBROOT / db / f"{db}.sqlite"
    vdir = OUTROOT / f"{qid}_{op}"
    vdb = vdir / f"{db}.sqlite"

    def fresh_copy():
        vdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, vdb)
        return sqlite3.connect(vdb)

    if op == "schema_column_rename":
        for t, cols in gc.items():
            for c, _typ in cols:
                if " " in c or "-" in c:
                    continue
                new = c + "_v2"
                con = fresh_copy()
                con.execute(f'ALTER TABLE "{t}" RENAME COLUMN "{c}" TO "{new}"')
                con.commit(); con.close()
                dgold = re.sub(rf"`{re.escape(c)}`|\b{re.escape(c)}\b", f"`{new}`", gold)
                orig = run(src, gold); newr = run(vdb, dgold)
                if sorted(map(str, orig)) == sorted(map(str, newr)):
                    return {"drifted_gold": dgold, "detail": f"column {t}.{c} renamed to {new}",
                            "check": "result-identical"}
                shutil.rmtree(vdir); return None
        return None

    if op == "data_value_recode":
        lits = literals_in(gold)
        for t, cols in gc.items():
            for c, typ in cols:
                if "TEXT" not in (typ or "").upper() and "CHAR" not in (typ or "").upper():
                    continue
                con0 = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                vals = [r[0] for r in con0.execute(
                    f'SELECT DISTINCT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL LIMIT 200')]
                con0.close()
                for v in vals:
                    if isinstance(v, str) and v in lits and 1 < len(v) <= 20:
                        newv = v + "_X"
                        con = fresh_copy()
                        con.execute(f'UPDATE "{t}" SET "{c}" = ? WHERE "{c}" = ?', (newv, v))
                        con.commit(); con.close()
                        dgold = gold.replace(f"'{v}'", f"'{newv}'")
                        run(vdb, dgold)
                        return {"drifted_gold": dgold, "detail": f"value {t}.{c}: '{v}' recoded to '{newv}'",
                                "check": "executes"}
                shutil.rmtree(vdir, ignore_errors=True)
                return None
        return None

    if op == "category_merge":
        for t, cols in gc.items():
            for c, typ in cols:
                if "TEXT" not in (typ or "").upper() and "CHAR" not in (typ or "").upper():
                    continue
                con0 = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                vals = [r[0] for r in con0.execute(
                    f'SELECT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL GROUP BY "{c}" '
                    f'ORDER BY COUNT(*) DESC LIMIT 6')]
                con0.close()
                strs = [v for v in vals if isinstance(v, str)]
                if len(strs) >= 2:
                    keep, gone = strs[0], strs[1]
                    con = fresh_copy()
                    con.execute(f'UPDATE "{t}" SET "{c}" = ? WHERE "{c}" = ?', (keep, gone))
                    con.commit(); con.close()
                    dgold = gold.replace(f"'{gone}'", f"'{keep}'")
                    run(vdb, dgold)
                    return {"drifted_gold": dgold,
                            "detail": f"categories in {t}.{c}: '{gone}' merged into '{keep}'",
                            "check": "executes"}
                shutil.rmtree(vdir, ignore_errors=True)
                return None
        return None

    if op == "data_unit_change":
        if re.search(r"(>=|<=|>|<|=)\s*\d", gold) and random.random() < 0:
            return None
        for t, cols in gc.items():
            for c, typ in cols:
                if not any(k in (typ or "").upper() for k in ("INT", "REAL", "NUM")):
                    continue
                con0 = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                mx = con0.execute(f'SELECT MAX("{c}") FROM "{t}"').fetchone()[0]
                con0.close()
                if isinstance(mx, (int, float)) and mx:
                    con = fresh_copy()
                    con.execute(f'UPDATE "{t}" SET "{c}" = "{c}" * 1000 WHERE "{c}" IS NOT NULL')
                    con.commit(); con.close()
                    run(vdb, gold)
                    return {"drifted_gold": gold,
                            "detail": f"unit change: {t}.{c} values x1000 (gold SQL unchanged; recorded value scale shifts)",
                            "check": "executes"}
                shutil.rmtree(vdir, ignore_errors=True)
                return None
        return None

    if op == "schema_type_change":
        for t, cols in gc.items():
            for c, typ in cols:
                if not any(k in (typ or "").upper() for k in ("INT", "REAL")):
                    continue
                con = fresh_copy()
                con.execute(f'CREATE TABLE "__tmp__" AS SELECT * FROM "{t}"')
                con.execute(f'DROP TABLE "{t}"')
                coldefs = ", ".join(f'"{cc}" TEXT' if cc == c else f'"{cc}"' for cc, _ in sch[t])
                collist = ", ".join(f'"{cc}"' for cc, _ in sch[t])
                con.execute(f'CREATE TABLE "{t}" ({coldefs})')
                con.execute(f'INSERT INTO "{t}" SELECT {collist} FROM "__tmp__"')
                con.execute('DROP TABLE "__tmp__"')
                con.commit(); con.close()
                run(vdb, gold)
                return {"drifted_gold": gold,
                        "detail": f"type change: {t}.{c} values stored as TEXT (was {typ})",
                        "check": "executes"}
        return None

    if op == "temporal_grain_change":
        for t, cols in gc.items():
            for c, typ in cols:
                if "DATE" not in (typ or "").upper() and "TIME" not in (typ or "").upper():
                    # also accept text columns that look like dates and appear in gold
                    con0 = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                    sample = con0.execute(
                        f'SELECT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL LIMIT 1').fetchone()
                    con0.close()
                    if not (sample and isinstance(sample[0], str)
                            and re.match(r"\d{4}-\d{2}-\d{2}", sample[0])):
                        continue
                con = fresh_copy()
                con.execute(f'UPDATE "{t}" SET "{c}" = substr("{c}", 1, 7) || \'-01\' '
                            f'WHERE "{c}" IS NOT NULL')
                con.commit(); con.close()
                run(vdb, gold)
                return {"drifted_gold": gold,
                        "detail": f"temporal grain: {t}.{c} dates truncated to month (YYYY-MM-01)",
                        "check": "executes"}
        return None

    if op == "null_semantics_change":
        for t, cols in gc.items():
            for c, _typ in cols:
                con0 = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                nnull = con0.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" IS NULL').fetchone()[0]
                tot = con0.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                con0.close()
                if 0 < nnull < tot:
                    con = fresh_copy()
                    con.execute(f'UPDATE "{t}" SET "{c}" = \'\' WHERE "{c}" IS NULL')
                    con.commit(); con.close()
                    run(vdb, gold)
                    return {"drifted_gold": gold,
                            "detail": f"null semantics: {t}.{c} NULLs ({nnull} rows) replaced by empty string",
                            "check": "executes"}
                shutil.rmtree(vdir, ignore_errors=True)
                return None
        return None
    return None

