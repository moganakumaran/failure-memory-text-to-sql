#!/usr/bin/env python3
"""Paper #1 pilot — shared library.
Implements Protocol S6 (memory spec) and S7 (fairness accounting):
- model backends: openai (connector helper, gpt-5-mini-2025-08-07) | ollama (local, smoke tests)
- budget ledger with hard stop (Amendments A6/A7: mini effort cap $7 total)
- read-only SQL execution with 10s limit (dry-run harness semantics, shared comparator)
- embeddings: local Ollama embed if available, else hashed TF vectors (recorded)
- episode store with the ACQUISITION POLICY enforced in code:
  an episode is stored only if the remediation was produced by the agent in-session
  AND execution-verified (ran + accepted by the agent's own verifier). Gold never
  enters an episode. Unresolved failures go to a separate log.
"""
import json, re, sqlite3, subprocess, sys, time, hashlib, math, pathlib, os

BASE = pathlib.Path(__file__).parent
HELPER = pathlib.Path(os.environ.get("OPENAI_HELPER", pathlib.Path.home() / "workspace/custom-connectors/custom.openai/bin/openai_api.py"))
DBROOT = BASE / "datasets/bird/dev_20240627/dev_databases/dev_databases"
DRIFTROOT = BASE / "datasets/bird_drift"
LEDGER = BASE / "pilot_spend.json"
MINI_IN, MINI_OUT = 0.25 / 1e6, 2.00 / 1e6   # gpt-5-mini list price
CAP_USD = 24.00                               # A8 $10 + A9 Stage 2 $10 (6.13 spent) + Amendment A14 fix runs
PRIOR_MINI_USD = 0.01                         # mini dry run, measured

# ---------------------------------------------------------------- budget
class BudgetStop(Exception):
    pass

def ledger_load():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"mini_usd": PRIOR_MINI_USD, "calls": 0, "note": "seeded with mini dry-run cost"}

def ledger_charge(usd, calls=1):
    import fcntl
    lock = open(LEDGER.with_suffix(".lock"), "w")
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        led = ledger_load()
        led["mini_usd"] = round(led["mini_usd"] + usd, 4)
        led["calls"] += calls
        tmp = LEDGER.with_suffix(".tmp")  # atomic rename: readers never see a truncated ledger (abl_A1_run4 died on a torn read, 2026-11-23)
        tmp.write_text(json.dumps(led, indent=1))
        os.replace(tmp, LEDGER)
        return led["mini_usd"]

def budget_check(est_usd):
    led = ledger_load()
    if led["mini_usd"] + est_usd > CAP_USD:
        raise BudgetStop(f"hard cap ${CAP_USD} would be exceeded "
                         f"(spent ${led['mini_usd']}, next est ${est_usd})")
    return led["mini_usd"]

# ---------------------------------------------------------------- model calls
def call_openai(prompt, model="gpt-5-mini-2025-08-07", max_tokens=4000):
    budget_check(0.02)  # conservative per-call estimate gate
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": max_tokens}
    t0 = time.time()
    out = None
    for attempt in range(2):  # one retry, only for transport/parse failures (never for API errors)
        p = subprocess.run([sys.executable, str(HELPER), "chat"], input=json.dumps(body),
                           capture_output=True, text=True, timeout=300)
        try:
            out = json.loads(p.stdout)
            break
        except Exception:
            print(f"[call_openai] non-JSON helper output (attempt {attempt}): "
                  f"rc={p.returncode} stdout={p.stdout[:200]!r} stderr={p.stderr[:200]!r}",
                  flush=True)
            if attempt == 1:
                raise RuntimeError("helper returned non-JSON twice; see log")
            time.sleep(5)
    if "error" in out:
        raise RuntimeError(f"API error: {json.dumps(out['error'])[:300]}")
    txt = out["choices"][0]["message"]["content"] or ""
    u = out.get("usage", {})
    pt, ot = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    usd = pt * MINI_IN + ot * MINI_OUT
    total = ledger_charge(usd)
    return txt, pt, ot, time.time() - t0, total

def call_ollama(prompt, model="qwen-coder-3b", max_tokens=1200):
    import urllib.request
    body = {"model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens}}
    t0 = time.time()
    req = urllib.request.Request("http://localhost:11434/api/generate",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return (out.get("response", ""), out.get("prompt_eval_count", 0),
            out.get("eval_count", 0), time.time() - t0, 0.0)

OR_HELPER = pathlib.Path(os.environ.get("OPENROUTER_HELPER", pathlib.Path.home() / "workspace/custom-connectors/custom.openrouter/bin/openrouter_api.py"))
REP_LEDGER = BASE / "pilot_spend_replication.json"
REP_CAP_USD = 10.00                           # Amendment A10 replication cap
# OpenRouter list price for qwen/qwen-2.5-coder-32b-instruct (Nov 2026 listings)
REP_USD_PER_IN = 0.66 / 1_000_000
REP_USD_PER_OUT = 1.00 / 1_000_000

def rep_ledger_load():
    if REP_LEDGER.exists():
        return json.loads(REP_LEDGER.read_text())
    return {"usd": 0.0, "calls": 0}

def rep_ledger_charge(usd, calls=1):
    import fcntl
    lock = open(REP_LEDGER.with_suffix(".lock"), "w")
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        led = rep_ledger_load()
        led["usd"] = round(led["usd"] + usd, 4)
        led["calls"] += calls
        REP_LEDGER.write_text(json.dumps(led, indent=1))
        return led["usd"]

def call_openrouter(prompt, model="qwen/qwen-2.5-coder-32b-instruct", max_tokens=4000):
    led = rep_ledger_load()
    if led["usd"] >= REP_CAP_USD:
        raise BudgetStop(f"replication cap ${REP_CAP_USD} reached (spent ${led['usd']})")
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens})
    t0 = time.time()
    last = None
    for attempt in range(2):
        p = subprocess.run([sys.executable, str(OR_HELPER), "chat"],
                           input=body, capture_output=True, text=True, timeout=300)
        try:
            out = json.loads(p.stdout)
        except Exception:
            out = {"error": f"non-JSON helper output rc={p.returncode}"}
        if "error" not in out:
            break
        last = out["error"]
        if attempt == 0:
            print(f"[call_openrouter] retry after: {str(last)[:160]}", file=sys.stderr)
            continue
        raise RuntimeError(f"OpenRouter API error: {last}")
    u = out.get("usage", {})
    pt = u.get("prompt_tokens", 0); ot = u.get("completion_tokens", 0)
    usd = pt * REP_USD_PER_IN + ot * REP_USD_PER_OUT
    rep_ledger_charge(usd)
    return (out["choices"][0]["message"]["content"], pt, ot, time.time() - t0, usd)

def make_caller(backend):
    if backend == "openai":
        return call_openai
    if backend == "openrouter":
        return call_openrouter
    return call_ollama

# ---------------------------------------------------------------- sql execution
def schema_text(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL").fetchall()
    con.close()
    return "\n".join(r[0] + ";" for r in rows)

def exec_sql(db_path, sql, limit=10.0):
    """Returns (rows|None, error|None). Read-only, interrupt after `limit` seconds."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    deadline = time.time() + limit
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
    try:
        rows = con.execute(sql).fetchmany(100000)
        return rows, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        con.close()

def results_equal(pred, gold, gold_sql):
    if pred is None or gold is None:
        return False
    if "order by" in gold_sql.lower():
        return [tuple(map(str, r)) for r in pred] == [tuple(map(str, r)) for r in gold]
    return sorted(map(str, pred)) == sorted(map(str, gold)) if False else \
        sorted(tuple(map(str, r)) for r in pred) == sorted(tuple(map(str, r)) for r in gold)

def extract_sql(text):
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    s = (m.group(1) if m else text).strip()
    m2 = re.search(r"(SELECT|WITH)\b.*", s, re.S | re.I)
    if m2:
        s = m2.group(0)
    return s.split(";")[0].strip() + ";"

# ---------------------------------------------------------------- text features
def tables_of(sql):
    s = sql.replace("`", " ").replace('"', " ")
    return frozenset(t.lower() for t in re.findall(r"(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.I))

def skeleton_tokens(sql):
    s = re.sub(r"'[^']*'", " ? ", sql.lower())
    s = re.sub(r"\b\d+(\.\d+)?\b", " # ", s)
    return frozenset(re.findall(r"[a-z_][a-z0-9_]*|[*(),.=<>+/%-]", s))

def q_tokens(q):
    return frozenset(re.findall(r"[a-z0-9]+", q.lower()))

def jac(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))

# ---------------------------------------------------------------- embeddings
_EMBED_MODE = None
def embed(text):
    """Frozen local embedding: Ollama qwen-coder-3b if it answers, else hashed TF.
    Mode is fixed on first use and recorded by the caller."""
    global _EMBED_MODE
    if _EMBED_MODE in ("ollama", "tf"):
        return _embed_tf(text) if _EMBED_MODE == "tf" else _embed_ollama(text)
    try:
        v = _embed_ollama(text)
        _EMBED_MODE = "ollama"
        return v
    except Exception:
        _EMBED_MODE = "tf"
        return _embed_tf(text)

def _embed_ollama(text):
    import urllib.request
    body = {"model": "qwen-coder-3b", "prompt": text}
    req = urllib.request.Request("http://localhost:11434/api/embeddings",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    v = out["embedding"]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def _embed_tf(text, dim=512):
    v = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def cosine(a, b):
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))

def embed_mode():
    return _EMBED_MODE

# ---------------------------------------------------------------- memory (Protocol S6)
def error_signature(err):
    if err is None:
        return "verifier-reject"
    e = err.lower()
    if "no such column" in e:
        return "no-such-column"
    if "no such table" in e:
        return "no-such-table"
    if "syntax" in e or "unrecognized" in e or "incomplete" in e:
        return "syntax"
    if "ambiguous" in e:
        return "ambiguous-column"
    return e.split(":")[-1].strip()[:60] or "exec-error"

def failure_class_of(sig):
    return {"no-such-column": "F1", "no-such-table": "F1", "ambiguous-column": "F1",
            "syntax": "F6", "verifier-reject": "F7"}.get(sig, "F6")

class EpisodeStore:
    """Raw episodic traces. Acquisition policy enforced by construction:
    add() is only called by the harness after an in-session, execution-verified
    remediation (see pilot.py). No gold anywhere in this class."""
    def __init__(self):
        self.episodes = []

    def add(self, *, db_id, question, schema_elements, error, failed_sql,
            remediation_sql, schema_version, run_id):
        sig = error_signature(error)
        ep = {
            "db_id": db_id,
            "intent": question,
            "schema_elements": sorted(schema_elements),
            "error": error,
            "error_signature": sig,
            "failure_class": failure_class_of(sig),
            "failed_sql": failed_sql,
            "remediation_sql": remediation_sql,
            "schema_version": schema_version,
            "run_id": run_id,
            "fingerprint": hashlib.sha256(json.dumps(
                [failure_class_of(sig), sig, sorted(schema_elements), schema_version],
                sort_keys=True).encode()).hexdigest()[:16],
            "embedding": embed(question + " " + " ".join(sorted(schema_elements))),
        }
        self.episodes.append(ep)
        return ep

    def retrieve_fingerprint(self, *, failure_sig, schema_elements, schema_version, k=3):
        cls = failure_class_of(failure_sig)
        hits = [e for e in self.episodes
                if e["failure_class"] == cls and e["error_signature"] == failure_sig
                and set(e["schema_elements"]) & set(schema_elements)]
        return hits[:k], [e["schema_version"] != schema_version for e in hits[:k]]

    def retrieve_embedding(self, *, question, schema_elements, db_id=None, k=3):
        qv = embed(question + " " + " ".join(sorted(schema_elements)))
        scored = []
        for e in self.episodes:
            if db_id is not None and e["db_id"] != db_id:
                continue
            scored.append((cosine(qv, e["embedding"]), e))
        scored.sort(key=lambda x: -x[0])
        return [e for _s, e in scored[:k]]

    def __len__(self):
        return len(self.episodes)

def episode_prompt_block(eps, with_meta=True):
    if not eps:
        return ""
    lines = ["\nRelevant past episodes from earlier tasks in this session "
             "(a failure the agent made, and the fix it found and verified by execution):"]
    for e in eps:
        meta = f" [failure class {e['failure_class']}; error: {e['error_signature']}]" if with_meta else ""
        lines.append(f"- Task: {e['intent']}{meta}\n  Failed SQL: {e['failed_sql']}\n"
                     f"  Error: {e['error']}\n  Verified fix: {e['remediation_sql']}")
    return "\n".join(lines) + "\n"
