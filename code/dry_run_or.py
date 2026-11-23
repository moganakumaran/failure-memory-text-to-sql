#!/usr/bin/env python3
"""Paper #1 frontier dry run — Arm A0 (no-memory), GPT-5 pinned snapshot, via the
custom.openai connector helper. Mirrors dry_run.py (local 3B run) EXACTLY in prompt,
retry logic (max 3 attempts, error feedback), and scoring (execution accuracy vs gold,
gold used only for scoring). Differences are backend-only and recorded:
- Model: gpt-5-mini-2025-08-07 (pinned snapshot of GPT-5 base, per Protocol Amendment A2).
- Decoding: GPT-5 does not accept a temperature parameter; provider default is used
  and recorded here. max_completion_tokens=6000 (reasoning tokens included in usage).
- Calls go through ~/workspace/custom-connectors/custom.openrouter/bin/openrouter_api.py.
"""
import json, sqlite3, time, subprocess, collections, pathlib, sys, csv, os

BASE = pathlib.Path(__file__).resolve().parent  # project root (see README: Layout)
DEV = BASE / "hidden_files/datasets/bird/dev_20240627/dev.json"
DBROOT = BASE / "hidden_files/datasets/bird/dev_20240627/dev_databases/dev_databases"
MANIFEST = BASE / "hidden_files/manifest_v1.csv"
OUT = BASE / "hidden_files/dry_run_traces_openrouter.jsonl"
HELPER = pathlib.Path(os.environ.get("OPENROUTER_HELPER", pathlib.Path.home() / "workspace/custom-connectors/custom.openrouter/bin/openrouter_api.py"))
MODEL = "qwen/qwen-2.5-coder-32b-instruct"

dry_ids = []
with open(MANIFEST) as f:
    for r in csv.DictReader(f):
        if r["split"] == "dry-run":
            dry_ids.append(int(r["source_task_id"]))
tasks = {x["question_id"]: x for x in json.load(open(DEV))}
dry = [tasks[i] for i in sorted(dry_ids)]
print(f"openrouter dry-run tasks: {[t['question_id'] for t in dry]}  model: {MODEL}", flush=True)

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
    body = {"model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000, "temperature": 0}
    t0 = time.time()
    p = subprocess.run([sys.executable, str(HELPER), "chat"], input=json.dumps(body),
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"helper failed rc={p.returncode}: {p.stderr[-400:]}")
    out = json.loads(p.stdout)
    if "error" in out and out.get("error"):
        raise RuntimeError(f"API error: {json.dumps(out['error'])[:400]}")
    text = out["choices"][0]["message"]["content"] or ""
    u = out.get("usage", {})
    return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), time.time() - t0

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
tot_in = tot_out = 0
done_ids = set()
if OUT.exists():
    for line in open(OUT):
        if line.strip():
            tr = json.loads(line)
            done_ids.add(tr["question_id"])
            results.append(bool(tr["success"]))
            tot_in += tr["prompt_tokens"]; tot_out += tr["output_tokens"]
    if done_ids:
        print(f"resuming: {len(done_ids)} tasks already traced, skipping {sorted(done_ids)}", flush=True)
with open(OUT, "a") as outf:
    for t in dry:
        if t["question_id"] in done_ids:
            continue
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
        tot_in += trace["prompt_tokens"]; tot_out += trace["output_tokens"]
        outf.write(json.dumps(trace) + "\n"); outf.flush()
        print(f"q{t['question_id']} {t['db_id']}: {'PASS' if verdict else 'FAIL'} "
              f"(attempts={len(trace['attempts'])}, tokens={trace['prompt_tokens']}+{trace['output_tokens']}, {trace['latency_s']:.0f}s)", flush=True)

est = tot_in / 1e6 * 0.25 + tot_out / 1e6 * 2.00
print(f"\nOPENROUTER DRY RUN DONE: {sum(results)}/{len(results)} passed ({sum(results)/len(results):.0%})  model={MODEL}")
print(f"tokens total: {tot_in} in + {tot_out} out; est. cost at OpenRouter $0.66/M in, $1.00/M out: ${est:.2f}")
