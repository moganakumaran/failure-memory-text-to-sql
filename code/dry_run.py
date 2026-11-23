#!/usr/bin/env python3
"""Paper #1 dry run — Arm A0 (no-memory single agent) on the 11 dry-run tasks.
Local model via Ollama HTTP API. Rules: Frozen Pilot Protocol v2.
- Agent loop: generate SQL from schema+question+evidence; execute read-only (10s limit);
  on execution error, feed the error back for a correction, max 3 attempts total.
- Verdict: execution accuracy — result set of final SQL vs gold SQL (order-insensitive
  unless the gold SQL contains ORDER BY), compared as multisets of rows.
- Gold SQL is used ONLY for scoring, never shown to the model and never stored as memory.
- Full trace logged per task to dry_run_traces.jsonl.
"""
import json, sqlite3, time, urllib.request, collections, pathlib, sys

BASE = pathlib.Path(__file__).resolve().parent  # project root (see README: Layout)
DEV = BASE / "hidden_files/datasets/bird/dev_20240627/dev.json"
DBROOT = BASE / "hidden_files/datasets/bird/dev_20240627/dev_databases/dev_databases"
MANIFEST = BASE / "hidden_files/manifest_v1.csv"
OUT = BASE / "hidden_files/dry_run_traces.jsonl"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:3b"
OLLAMA = "http://localhost:11434/api/generate"

import csv
dry_ids = []
with open(MANIFEST) as f:
    for r in csv.DictReader(f):
        if r["split"] == "dry-run":
            dry_ids.append(int(r["source_task_id"]))
tasks = {x["question_id"]: x for x in json.load(open(DEV))}
dry = [tasks[i] for i in sorted(dry_ids)]
print(f"dry-run tasks: {[t['question_id'] for t in dry]}  model: {MODEL}", flush=True)

def schema_of(db_id):
    con = sqlite3.connect(f"file:{DBROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
    rows = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL").fetchall()
    con.close()
    return "\n".join(r[0] + ";" for r in rows)

def run_sql(db_id, sql, limit_s=10):
    con = sqlite3.connect(f"file:{DBROOT}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
    deadline = time.time() + limit_s
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
    try:
        rows = con.execute(sql).fetchall()
        return rows, None
    except Exception as e:
        return None, str(e)[:300]
    finally:
        con.close()

def call_model(prompt):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read())
    return out["response"], out.get("prompt_eval_count", 0), out.get("eval_count", 0), time.time() - t0

def extract_sql(text):
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        for p in parts:
            if "SELECT" in p.upper():
                t = p
                break
    idx = t.upper().find("SELECT")
    if idx >= 0:
        t = t[idx:]
    return t.split(";")[0].strip() + ";"

def result_match(db_id, pred_sql, gold_sql):
    gold_rows, gerr = run_sql(db_id, gold_sql, limit_s=30)
    if gerr:
        return None, f"gold failed: {gerr}"
    pred_rows, perr = run_sql(db_id, pred_sql)
    if perr:
        return False, perr
    if "ORDER BY" in gold_sql.upper():
        return list(pred_rows) == list(gold_rows), None
    return collections.Counter(pred_rows) == collections.Counter(gold_rows), None

results = []
with open(OUT, "w") as outf:
    for t in dry:
        schema = schema_of(t["db_id"])
        base_prompt = (
            "You are a data analyst. Given the SQLite schema below and a question, write ONE SQLite SQL query that answers it.\n"
            "Output ONLY the SQL query, no explanation.\n\n"
            f"Schema:\n{schema}\n\n"
            f"Evidence: {t['evidence']}\nQuestion: {t['question']}\nSQL:"
        )
        trace = {"question_id": t["question_id"], "db_id": t["db_id"], "question": t["question"],
                 "model": MODEL, "attempts": [], "prompt_tokens": 0, "output_tokens": 0, "latency_s": 0.0}
        prompt = base_prompt
        verdict = False
        for attempt in range(3):
            raw, ptok, otok, lat = call_model(prompt)
            sql = extract_sql(raw)
            trace["prompt_tokens"] += ptok; trace["output_tokens"] += otok; trace["latency_s"] += lat
            rows, err = run_sql(t["db_id"], sql)
            trace["attempts"].append({"sql": sql, "exec_error": err, "raw": raw[:500]})
            if err is None:
                m, merr = result_match(t["db_id"], sql, t["SQL"])
                verdict = bool(m)
                trace["result_match"] = m
                break
            prompt = base_prompt + f"\n\nYour previous SQL:\n{sql}\nIt produced this error: {err}\nWrite a corrected SQL query. Output ONLY the SQL:"
        else:
            trace["result_match"] = False
        trace["success"] = verdict
        results.append(verdict)
        outf.write(json.dumps(trace) + "\n"); outf.flush()
        print(f"q{t['question_id']} {t['db_id']}: {'PASS' if verdict else 'FAIL'} "
              f"(attempts={len(trace['attempts'])}, tokens={trace['prompt_tokens']}+{trace['output_tokens']}, {trace['latency_s']:.0f}s)", flush=True)

print(f"\nDRY RUN DONE: {sum(results)}/{len(results)} passed ({sum(results)/len(results):.0%})  model={MODEL}")
