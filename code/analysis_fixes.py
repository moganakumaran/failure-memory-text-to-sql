#!/usr/bin/env python3
"""Amendment A14 offline analyses (no new model calls):
1. pass^k (tau-bench estimator C(c,k)/C(n,k), n=4 runs) for the primary contrasts.
2. A1 retrieval-path analysis: fingerprint-path hits (trace entries carrying a
   'stale' key, produced by retrieve_fingerprint after an observed failure) vs
   embedding-path retrievals (pre-task retrieve_embedding).
3. Drift-arm acquisition: A4 pre-drift store sizes per run, A1 drift-phase growth.
Outputs fixes_results.json. Seed 20261122 for bootstrap CIs.
"""
import json, glob, math, random, pathlib
from collections import defaultdict

HF = pathlib.Path(__file__).parent
random.seed(20261122)
RECALL_CONTROL = {850, 1326, 1479}

def load(pattern, phase=None, arm=None):
    rows = []
    for f in sorted(glob.glob(str(HF / pattern))):
        if 'starved' in f or 'smoke' in f:
            continue
        for l in open(f):
            t = json.loads(l)
            if phase and t.get('phase') != phase: continue
            if arm and t.get('arm') != arm: continue
            rows.append(t)
    return rows

def passk(rows, label='pass_original', tasks=None):
    """tau-bench pass^k estimator per task, averaged. Returns {k: value}."""
    by_task = defaultdict(list)
    for t in rows:
        if tasks is not None and t['qid'] not in tasks: continue
        v = t.get(label)
        if v is None: continue
        by_task[t['qid']].append(1 if v else 0)
    out = {}
    for k in (1, 2, 4):
        vals = []
        for qid, runs in by_task.items():
            n, c = len(runs), sum(runs)
            if n < k: continue
            vals.append(math.comb(c, k) / math.comb(n, k))
        out[f'pass^{k}'] = round(sum(vals) / len(vals), 4) if vals else None
        out[f'n_tasks_pass^{k}'] = len(vals)
    return out

def boot_diff(rows_a, rows_b, label='pass_original', tasks=None, k=None):
    """Paired per-task difference (b - a) of run-mean pass@1 (k=None) or pass^k
    estimator, task-level bootstrap 95% CI."""
    def per_task(rows):
        d = defaultdict(list)
        for t in rows:
            if tasks is not None and t['qid'] not in tasks: continue
            v = t.get(label)
            if v is None: continue
            d[t['qid']].append(1 if v else 0)
        return d
    da, db = per_task(rows_a), per_task(rows_b)
    common = sorted(set(da) & set(db))
    def val(runs):
        n, c = len(runs), sum(runs)
        if k is None: return c / n
        return math.comb(c, k) / math.comb(n, k) if n >= k else None
    diffs = []
    for q in common:
        va, vb = val(da[q]), val(db[q])
        if va is None or vb is None: continue
        diffs.append(vb - va)
    point = sum(diffs) / len(diffs)
    boots = []
    for _ in range(10000):
        s = [diffs[random.randrange(len(diffs))] for _ in diffs]
        boots.append(sum(s) / len(s))
    boots.sort()
    return {'tasks': len(diffs), 'diff': round(point, 4),
            'ci95': [round(boots[250], 4), round(boots[9750], 4)]}

R = {}

# ---- 1. pass^k: mini repeated split (97 primary S2 tasks) ----
mini = {}
for arm, pat in [('A0', 'traces_stage1_A0_run*.jsonl'), ('A1', 'traces_stage1_A1_run*.jsonl'),
                 ('A2', 'traces_stage2_A2_run*.jsonl'), ('A3', 'traces_stage2_A3_run*.jsonl')]:
    mini[arm] = load(pat, phase='S2')
all_s2 = {t['qid'] for t in mini['A0']}
primary = all_s2 - RECALL_CONTROL
R['mini_passk_original'] = {a: passk(r, 'pass_original', primary) for a, r in mini.items()}
R['mini_passk_corrected'] = {a: passk(r, 'pass_corrected', primary) for a, r in mini.items()}
R['mini_A1_minus_A0_passk'] = {f'pass^{k}': boot_diff(mini['A0'], mini['A1'], 'pass_original', primary, k)
                              for k in (2, 4)}
R['mini_A1_minus_A0_passk_corrected'] = {f'pass^{k}': boot_diff(mini['A0'], mini['A1'], 'pass_corrected', primary, k)
                                         for k in (2, 4)}

# ---- 1b. pass^k: Qwen replication ----
rep = {a: load(f'traces_rep_{a}_run*.jsonl', phase='S2') for a in ('A0', 'A1', 'A3')}
R['rep_passk_original'] = {a: passk(r, 'pass_original', primary) for a, r in rep.items()}
R['rep_A1_minus_A0_passk'] = {f'pass^{k}': boot_diff(rep['A0'], rep['A1'], 'pass_original', primary, k)
                              for k in (2, 4)}

# ---- 1c. pass^k: drift split (60 tasks, phase 'drift') ----
drift = {a: load('traces_stage2_drift_run*.jsonl', phase='drift', arm=a) for a in ('A0', 'A1', 'A4')}
R['drift_passk_original'] = {a: passk(r, 'pass_original') for a, r in drift.items()}
R['drift_A4_minus_A0_passk'] = {f'pass^{k}': boot_diff(drift['A0'], drift['A4'], 'pass_original', None, k)
                                for k in (2, 4)}

# ---- 2. A1 retrieval-path analysis ----
def retrieval_stats(rows_s2, label):
    n = len(rows_s2)
    with_any = sum(1 for t in rows_s2 if t['retrieved'])
    fp_hits = [t for t in rows_s2 if any('stale' in e for e in t['retrieved'])]
    emb_only = [t for t in rows_s2 if t['retrieved'] and not any('stale' in e for e in t['retrieved'])]
    total_eps = sum(len(t['retrieved']) for t in rows_s2)
    fp_eps = sum(sum(1 for e in t['retrieved'] if 'stale' in e) for t in rows_s2)
    return {f'{label}_s2_trajectories': n,
            'with_any_retrieval': with_any,
            'with_fingerprint_hit': len(fp_hits),
            'embedding_only': len(emb_only),
            'episodes_retrieved_total': total_eps,
            'episodes_via_fingerprint': fp_eps,
            'episodes_via_embedding': total_eps - fp_eps}
R['retrieval_mini_A1'] = retrieval_stats(mini['A1'], 'mini')
R['retrieval_rep_A1'] = retrieval_stats(rep['A1'], 'rep')
a2 = load('traces_stage2_A2_run*.jsonl', phase='S2')
R['retrieval_mini_A2'] = retrieval_stats(a2, 'mini')

# ---- 3. Drift-arm acquisition ----
pre = load('traces_stage2_drift_run*.jsonl', phase='pre', arm='A4')
per_run_store = {}
for rid in ('run1', 'run2', 'run3', 'run4'):
    rows = [t for t in pre if t['run_id'] == rid]
    if rows:
        per_run_store[rid] = {'trajectories': len(rows),
                              'episodes_acquired': sum(t['acquired_episode'] for t in rows),
                              'pass1_original': round(sum(t['pass_original'] for t in rows) / len(rows), 4)}
R['a4_predrift'] = per_run_store
a1d = drift['A1']
R['a1_drift_phase'] = {'trajectories': len(a1d),
                       'episodes_acquired_during_drift': sum(t['acquired_episode'] for t in a1d)}
# A4 drift-phase: store frozen; confirm no acquisitions recorded
a4d = drift['A4']
R['a4_drift_phase'] = {'trajectories': len(a4d),
                       'episodes_acquired_during_drift': sum(t['acquired_episode'] for t in a4d)}

json.dump(R, open(HF / 'fixes_results.json', 'w'), indent=1)
print(json.dumps(R, indent=1))
