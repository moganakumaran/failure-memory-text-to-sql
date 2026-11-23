#!/usr/bin/env python3
"""Paper #1 pilot harness — Protocol S3/S4/S6/S7 as frozen (Amendments A1-A7).

Base agent (identical across arms): generate SQL -> execute (read-only, 10s) ->
on error, error feedback retry; on success, the agent's own verifier ACCEPTs or
REVISEs with a corrected SQL. Max 3 attempts per task. The verifier is what makes
Protocol S6's "execution-verified" acquisition meaningful: an episode is stored
only when an in-session failure is followed by an attempt that executes AND is
verifier-accepted. Gold is used ONLY for offline scoring, never in prompts/episodes.

Recorded interpretation (flagged for the pilot report): on the repeated split,
retrieval in Phase 2 uses the store frozen at the Session-1 boundary (leakage
rule, S3a); on the drift split, A1's store additionally grows with episodes
acquired earlier within the drift phase (sequential task order), while A4's
store is frozen pre-drift and never updated (S3b/S4 contrast).

Usage: pilot.py --backend ollama|openai --split repeated|drift
       [--arms A0,A1,A2,A3,A4] [--runs 4] [--limit-pairs N] [--a1-avg-tokens N]
       [--out TAG]
"""
import argparse, csv, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pilot_lib as L

HF = pathlib.Path(__file__).parent
MAX_ATTEMPTS = 3

DEV = {x["question_id"]: x for x in json.load(open(HF / "datasets/bird/dev_20240627/dev.json"))}
MAN = {int(r["source_task_id"]): r for r in csv.DictReader(open(HF / "manifest_v2.csv"))}

GEN_PROMPT = """You are a data analyst. Write a single SQLite query that answers the question, using only the database schema below.

Database schema:
{schema}

{evidence_block}{memory_block}Question: {question}

Output only the SQL query, no explanation."""

VERIFY_PROMPT = """You are checking your own work. Question: {question}

Your SQL:
{sql}

It executed without error and returned {nrows} row(s). First rows: {preview}

Does this result plausibly and completely answer the question (right entities, right columns, sensible values)?
Reply with exactly ACCEPT if yes. If not, reply REVISE on the first line, then the corrected SQL only."""

def gen_prompt(db_path, task, memory_block=""):
    ev = task.get("evidence") or ""
    return GEN_PROMPT.format(schema=L.schema_text(db_path),
                             evidence_block=(f"Hint: {ev}\n" if ev else ""),
                             memory_block=memory_block, question=task["question"])

def run_task(call, db_path, task, *, arm, store=None, frozen_store=None,
             acquire=True, run_id="r0", a1_avg_tokens=None, verifier=True):
    """One trajectory. Returns trace dict. store: live EpisodeStore (Phase 1);
    frozen_store: list snapshot for retrieval-only phases."""
    qid = task["question_id"]
    schema_elems = set()
    t_in = t_out = 0
    attempts = []
    memory_block = ""
    retrieved_meta = []
    active_store = store if store is not None else None
    retrieval_pool = None
    if frozen_store is not None:
        retrieval_pool = frozen_store  # list of episode dicts
    def pool_eps():
        if retrieval_pool is not None:
            return retrieval_pool
        return active_store.episodes if active_store is not None else []
    if arm in ("A1", "A2", "A4") :
        eps = L.EpisodeStore()
        eps.episodes = pool_eps()
        got = eps.retrieve_embedding(question=task["question"], schema_elements=set(),
                                     db_id=task["db_id"], k=3)
        memory_block = L.episode_prompt_block(got, with_meta=(arm != "A2"))
        retrieved_meta = [{"fp": g["fingerprint"], "cls": g["failure_class"]} for g in got]
    prompt = gen_prompt(db_path, task, memory_block)
    answer_sql, accepted = None, False
    failures = []   # (error_text, failed_sql)
    lat = 0.0
    pending_sql = None
    for att in range(MAX_ATTEMPTS):
        if pending_sql is not None:
            sql, pending_sql = pending_sql, None
        else:
            txt, pt, ot, dt, _sp = call(prompt)
            t_in += pt; t_out += ot; lat += dt
            sql = L.extract_sql(txt)
        rows, err = L.exec_sql(db_path, sql)
        if err is not None:
            attempts.append({"sql": sql, "exec_error": err, "verdict": None})
            failures.append((err, sql))
            if att == MAX_ATTEMPTS - 1:
                answer_sql = sql
                break
            prompt = (f"Your previous SQL failed to execute.\nSQL: {sql}\nError: {err}\n"
                      f"Write a corrected single SQLite query for the question: {task['question']}\n"
                      f"Use only this schema:\n{L.schema_text(db_path)}\nOutput only the SQL.")
            # fingerprint re-retrieval after an observed failure (A1/A4 only)
            if arm in ("A1", "A4") and failures:
                eps = L.EpisodeStore(); eps.episodes = pool_eps()
                hits, stale = eps.retrieve_fingerprint(
                    failure_sig=L.error_signature(err),
                    schema_elements=L.tables_of(sql), schema_version="v1", k=3)
                if hits:
                    prompt += L.episode_prompt_block(hits, with_meta=True)
                    retrieved_meta += [{"fp": h["fingerprint"], "cls": h["failure_class"],
                                        "stale": s} for h, s in zip(hits, stale)]
            continue
        # executed -> verifier (Amendment A14 ablation: verifier=False accepts
        # the first executed SQL; acquisition can then only trigger on
        # execution-error recoveries, never on verifier rejections)
        if not verifier:
            attempts.append({"sql": sql, "exec_error": None, "verdict": "no_verifier"})
            answer_sql, accepted = sql, True
            break
        preview = str(rows[:5])[:300]
        vprompt = VERIFY_PROMPT.format(question=task["question"], sql=sql,
                                       nrows=len(rows), preview=preview)
        vtxt, pt, ot, dt, _sp = call(vprompt)
        t_in += pt; t_out += ot; lat += dt
        if vtxt.strip().upper().startswith("ACCEPT"):
            attempts.append({"sql": sql, "exec_error": None, "verdict": "accept"})
            answer_sql, accepted = sql, True
            break
        rev_sql = L.extract_sql(vtxt) if ("SELECT" in vtxt.upper() or "WITH" in vtxt.upper()) else None
        attempts.append({"sql": sql, "exec_error": None, "verdict": "revise"})
        failures.append((None, sql))  # verifier-reject counts as an observed failure (F7-type)
        if att == MAX_ATTEMPTS - 1 or rev_sql is None or rev_sql == sql:
            answer_sql = sql
            break
        pending_sql = rev_sql  # the verifier's own corrected SQL is the next attempt (no extra call)
    # ---- acquisition (Protocol S6) ----
    acquired = False
    if acquire and accepted and failures and active_store is not None:
        err0, failed_sql0 = failures[0]
        active_store.add(db_id=task["db_id"], question=task["question"],
                         schema_elements=L.tables_of(failed_sql0 or answer_sql),
                         error=err0 or "verifier rejected the result as not answering the question",
                         failed_sql=failed_sql0, remediation_sql=answer_sql,
                         schema_version="v1", run_id=run_id)
        acquired = True
    unresolved = bool(failures) and not accepted
    # ---- offline scoring (gold never above this line) ----
    gold_rows, _ = L.exec_sql(db_path, task["SQL"])
    pred_rows, _ = L.exec_sql(db_path, answer_sql) if answer_sql else (None, "no answer")
    ok_orig = L.results_equal(pred_rows, gold_rows, task["SQL"])
    ok_corr = None
    corr_sql = MAN[qid].get("gold_sql_corrected") if qid in MAN else None
    if corr_sql:
        crows, _ = L.exec_sql(db_path, corr_sql)
        ok_corr = L.results_equal(pred_rows, crows, corr_sql)
    return {"qid": qid, "db_id": task["db_id"], "arm": arm, "run_id": run_id,
            "attempts": attempts, "n_attempts": len(attempts), "accepted": accepted,
            "acquired_episode": acquired, "unresolved_failure": unresolved,
            "tokens_in": t_in, "tokens_out": t_out, "latency_s": round(lat, 1),
            "retrieved": retrieved_meta, "pass_original": ok_orig, "pass_corrected": ok_corr,
            "answer_sql": answer_sql, "no_verifier": (not verifier)}

def _budgeted_call(call, prompt, spent, cap):
    """One call whose output is capped so the WHOLE trajectory stays within cap
    (Amendment A10 fix: Stage 2's A3 overshot because the selector call sat
    outside the cap check). Returns (txt, pt, ot, dt) or None if the call
    cannot fit the remaining budget."""
    if cap is None:
        txt, pt, ot, dt, _ = call(prompt)
        return txt, pt, ot, dt
    est_in = int(len(prompt) / 3.5) + 64
    remaining = cap - spent - est_in
    if remaining < 64:
        return None
    txt, pt, ot, dt, _ = call(prompt, max_tokens=min(2600, remaining))
    return txt, pt, ot, dt

def run_task_a3(call, db_path, task, *, run_id="r0", token_cap=None):
    """Generate-and-select: 3 candidates, executed, selector picks; verifier on the pick."""
    qid = task["question_id"]
    t_in = t_out = 0; lat = 0.0
    cap_fallback = False
    cap_mercy = False
    base_prompt = gen_prompt(db_path, task)
    cands = []
    for _i in range(3):
        r = _budgeted_call(call, base_prompt, t_in + t_out, token_cap)
        if r is None:
            cap_fallback = True
            break
        txt, pt, ot, dt = r
        t_in += pt; t_out += ot; lat += dt
        sql = L.extract_sql(txt)
        rows, err = L.exec_sql(db_path, sql)
        cands.append({"sql": sql, "err": err, "nrows": (len(rows) if rows is not None else None),
                      "preview": (str(rows[:3])[:150] if rows else "")})
    if not cands and token_cap is not None:
        # Mercy rule (Amendment A13): the pre-call estimator blocked even the
        # FIRST candidate on large-schema tasks (36% of trajectories under the
        # original len/3 estimator). An arm that returns empty SQL on a third
        # of tasks tests the estimator, not generate-and-select. Allow exactly
        # one capped call so the arm always produces a candidate; the breach
        # is bounded (max_tokens=384 plus the prompt) and flagged in the trace.
        cap_mercy = True
        txt, pt, ot, dt, _ = call(base_prompt, max_tokens=384)
        t_in += pt; t_out += ot; lat += dt
        sql = L.extract_sql(txt)
        rows, err = L.exec_sql(db_path, sql)
        cands.append({"sql": sql, "err": err, "nrows": (len(rows) if rows is not None else None),
                      "preview": (str(rows[:3])[:150] if rows else "")})
    ok_cands = [c for c in cands if c["err"] is None]
    if not ok_cands:
        answer_sql, accepted = (cands[0]["sql"], False) if cands else ("", False)
    else:
        listing = "\n".join(f"Candidate {i+1}: {c['sql']}\n  -> {c['nrows']} rows: {c['preview']}"
                            for i, c in enumerate(ok_cands))
        sprompt = (f"Question: {task['question']}\n\nCandidate queries that executed:\n{listing}\n\n"
                   f"Reply with only the number of the candidate whose result best answers the question.")
        r = _budgeted_call(call, sprompt, t_in + t_out, token_cap)
        if r is None:
            cap_fallback = True
            answer_sql, accepted = ok_cands[0]["sql"], True
        else:
            stxt, pt, ot, dt = r
            t_in += pt; t_out += ot; lat += dt
            import re as _re
            m = _re.search(r"[1-9]", stxt)
            pick = ok_cands[int(m.group(0)) - 1] if m and int(m.group(0)) <= len(ok_cands) else ok_cands[0]
            answer_sql, accepted = pick["sql"], True
    gold_rows, _ = L.exec_sql(db_path, task["SQL"])
    pred_rows, _ = L.exec_sql(db_path, answer_sql)
    ok_orig = L.results_equal(pred_rows, gold_rows, task["SQL"])
    ok_corr = None
    corr_sql = MAN[qid].get("gold_sql_corrected") if qid in MAN else None
    if corr_sql:
        crows, _ = L.exec_sql(db_path, corr_sql)
        ok_corr = L.results_equal(pred_rows, crows, corr_sql)
    return {"qid": qid, "db_id": task["db_id"], "arm": "A3", "run_id": run_id,
            "attempts": [{"sql": c["sql"], "exec_error": c["err"], "verdict": None} for c in cands],
            "n_attempts": len(cands), "accepted": accepted, "acquired_episode": False,
            "unresolved_failure": not accepted, "tokens_in": t_in, "tokens_out": t_out,
            "latency_s": round(lat, 1), "retrieved": [], "pass_original": ok_orig,
            "pass_corrected": ok_corr, "answer_sql": answer_sql,
            "cap_fallback": cap_fallback, "cap_mercy": cap_mercy}

def _load_done(path):
    done = set()
    if path.exists():
        for line in open(path):
            if line.strip():
                t = json.loads(line)
                done.add((t["arm"], t["run_id"], t["phase"], t["qid"]))
    return done

def _rebuild_store(journal_path, arm, run_id, phase):
    """Rebuild an EpisodeStore from journaled episodes (embeddings recomputed)."""
    store = L.EpisodeStore()
    if journal_path.exists():
        for line in open(journal_path):
            if not line.strip():
                continue
            e = json.loads(line)
            if e["arm"] == arm and e["run_id"] == run_id and e["phase"] == phase:
                ep = e["episode"]
                ep["embedding"] = L.embed(ep["intent"] + " " + " ".join(ep["schema_elements"]))
                store.episodes.append(ep)
    return store

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ollama")
    ap.add_argument("--split", default="repeated")
    ap.add_argument("--arms", default="A0,A1")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--only-run", type=int, default=None)
    ap.add_argument("--limit-pairs", type=int, default=None)
    ap.add_argument("--a1-avg-tokens", type=int, default=None)
    ap.add_argument("--no-verifier", action="store_true",
                    help="Amendment A14 ablation: disable the self-verifier")
    ap.add_argument("--undrifted", action="store_true",
                    help="Amendment A14 F1 control: with --split drift, run A0 on the ORIGINAL databases (phase 'undrifted')")
    ap.add_argument("--out", default="pilot")
    args = ap.parse_args()
    call = L.make_caller(args.backend)
    arms = args.arms.split(",")
    traces_path = HF / f"traces_{args.out}.jsonl"
    journal_path = HF / f"episodes_{args.out}.jsonl"
    done = _load_done(traces_path)
    out = open(traces_path, "a")
    journal = open(journal_path, "a")

    def journal_new(store, arm, rid, phase, seen):
        while len(store.episodes) > seen:
            ep = {k: v for k, v in store.episodes[seen].items() if k != "embedding"}
            journal.write(json.dumps({"arm": arm, "run_id": rid, "phase": phase,
                                      "episode": ep}) + "\n")
            journal.flush()
            seen += 1
        return seen

    def emit(tr, phase):
        key = (tr["arm"], tr["run_id"], phase, tr["qid"])
        if key in done:
            return False
        tr["split"] = args.split; tr["phase"] = phase
        out.write(json.dumps(tr) + "\n"); out.flush()
        done.add(key)
        print(f"[{args.split}/{tr['arm']}/{tr['run_id']}/{phase}] q{tr['qid']}: "
              f"{'PASS' if tr['pass_original'] else 'fail'} att={tr['n_attempts']} "
              f"tok={tr['tokens_in']+tr['tokens_out']} acq={tr['acquired_episode']}", flush=True)
        return True

    run_ids = [args.only_run] if args.only_run else list(range(1, args.runs + 1))
    try:
        if args.split == "repeated":
            pairs = list(csv.DictReader(open(HF / "splits_repeated.csv")))
            if args.limit_pairs:
                pairs = pairs[:args.limit_pairs]
            for run in run_ids:
                rid = f"run{run}"
                for arm in [a for a in arms if a != "A3"]:
                    store = _rebuild_store(journal_path, arm, rid, "S1") \
                        if arm in ("A1", "A2") else None
                    seen = len(store.episodes) if store is not None else 0
                    for p in pairs:  # Phase 1
                        t = DEV[int(p["session1_qid"])]
                        if (arm, rid, "S1", t["question_id"]) in done:
                            continue
                        dbp = L.DBROOT / t["db_id"] / f"{t['db_id']}.sqlite"
                        emit(run_task(call, dbp, t, arm=arm, store=store, run_id=rid,
                                      verifier=not args.no_verifier), "S1")
                        if store is not None:
                            seen = journal_new(store, arm, rid, "S1", seen)
                    frozen = list(store.episodes) if store is not None else None
                    shadow = L.EpisodeStore()  # Phase-2 acquisitions counted, never retrieved
                    seen2 = 0
                    for p in pairs:  # Phase 2
                        t = DEV[int(p["session2_qid"])]
                        if (arm, rid, "S2", t["question_id"]) in done:
                            continue
                        dbp = L.DBROOT / t["db_id"] / f"{t['db_id']}.sqlite"
                        emit(run_task(call, dbp, t, arm=arm, store=shadow,
                                      frozen_store=frozen, run_id=rid,
                                      verifier=not args.no_verifier,
                                      acquire=(arm in ("A1", "A2"))), "S2")
                        seen2 = journal_new(shadow, arm, rid, "S2", seen2)
                if "A3" in arms:
                    for p in pairs:
                        t = DEV[int(p["session2_qid"])]
                        if ("A3", rid, "S2", t["question_id"]) in done:
                            continue
                        dbp = L.DBROOT / t["db_id"] / f"{t['db_id']}.sqlite"
                        emit(run_task_a3(call, dbp, t, run_id=rid,
                                         token_cap=args.a1_avg_tokens), "S2")
        elif args.split == "drift" and args.undrifted:
            # Amendment A14 F1 control: A0 on the ORIGINAL databases for the
            # drift task set, so the drift effect is a paired contrast on
            # identical tasks (original gold, original DB paths).
            spec = list(csv.DictReader(open(HF / "drift_spec.csv")))
            if args.limit_pairs:
                spec = spec[:args.limit_pairs]
            for run in run_ids:
                rid = f"run{run}"
                for s in spec:
                    qid = int(s["qid"])
                    if ("A0", rid, "undrifted", qid) in done:
                        continue
                    t = DEV[qid]
                    dbp = L.DBROOT / t["db_id"] / f"{t['db_id']}.sqlite"
                    emit(run_task(call, dbp, t, arm="A0", run_id=rid), "undrifted")
        elif args.split == "drift":
            spec = list(csv.DictReader(open(HF / "drift_spec.csv")))
            if args.limit_pairs:
                spec = spec[:args.limit_pairs]
            for run in run_ids:
                rid = f"run{run}"
                # A4 pre-drift phase: acquire on the ORIGINAL databases, then freeze.
                pre_store = _rebuild_store(journal_path, "A4", rid, "pre")
                seen_pre = len(pre_store.episodes)
                if "A4" in arms:
                    for s in spec:
                        qid = int(s["qid"])
                        if ("A4", rid, "pre", qid) in done:
                            continue
                        t = DEV[qid]
                        dbp = L.DBROOT / t["db_id"] / f"{t['db_id']}.sqlite"
                        emit(run_task(call, dbp, t, arm="A4", store=pre_store,
                                      run_id=rid, acquire=True), "pre")
                        seen_pre = journal_new(pre_store, "A4", rid, "pre", seen_pre)
                frozen_pre = list(pre_store.episodes)
                for arm in [a for a in arms if a in ("A0", "A1", "A4")]:
                    live = _rebuild_store(journal_path, arm, rid, "drift") \
                        if arm == "A1" else None
                    seen = len(live.episodes) if live is not None else 0
                    shadow = L.EpisodeStore()
                    for s in spec:
                        qid = int(s["qid"])
                        if (arm, rid, "drift", qid) in done:
                            continue
                        base = DEV[qid]
                        t = dict(base); t["SQL"] = s["drifted_gold_sql"]
                        if arm == "A1":
                            tr = run_task(call, s["drifted_db_path"], t, arm="A1",
                                          store=live, run_id=rid, acquire=True)
                            seen = journal_new(live, "A1", rid, "drift", seen)
                        elif arm == "A4":
                            tr = run_task(call, s["drifted_db_path"], t, arm="A4",
                                          store=shadow, frozen_store=frozen_pre,
                                          run_id=rid, acquire=False)
                        else:
                            tr = run_task(call, s["drifted_db_path"], t, arm="A0",
                                          run_id=rid)
                        emit(tr, "drift")
        else:
            raise SystemExit(f"unknown split {args.split}")
    except L.BudgetStop as e:
        print(f"STOPPED (budget): {e}", flush=True)
    except RuntimeError as e:
        print(f"STOPPED (API): {e}", flush=True)
    out.close(); journal.close()
    print(f"DONE/STOPPED. ledger: {L.ledger_load()}", flush=True)

if __name__ == "__main__":
    main()
