#!/usr/bin/env python3
"""Amendment A15 analysis: store-transplant verifier ablation (arm A1-T).
Paired per-task run-mean pass@1 differences, task-level bootstrap 95% CIs,
seed 20261122 (same method as analysis_a14.py). Comparators are the EXISTING
A14 no-verifier runs (traces_abl_*), reused from stored traces, not re-run.
Output: mvr_a15.json (+ printed summary)."""
import json, glob, random, pathlib
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

def per_task(rows, label, tasks=None):
    d = defaultdict(list)
    for t in rows:
        if tasks is not None and t['qid'] not in tasks: continue
        v = t.get(label)
        if v is None: continue
        d[t['qid']].append(1 if v else 0)
    return {q: sum(v) / len(v) for q, v in d.items()}

def paired_diff(rows_a, rows_b, label, tasks=None):
    """b minus a, paired by task, bootstrap CI (mirrors analysis_a14.py)."""
    da, db = per_task(rows_a, label, tasks), per_task(rows_b, label, tasks)
    common = sorted(set(da) & set(db))
    diffs = [db[q] - da[q] for q in common]
    point = sum(diffs) / len(diffs)
    boots = []
    for _ in range(10000):
        s = [diffs[random.randrange(len(diffs))] for _ in diffs]
        boots.append(sum(s) / len(s))
    boots.sort()
    return {'tasks': len(common), 'diff': round(point, 4),
            'ci95': [round(boots[250], 4), round(boots[9750], 4)]}

def level(rows, label, tasks=None):
    pt = per_task(rows, label, tasks)
    return {'tasks': len(pt), 'pass1': round(sum(pt.values()) / len(pt), 4)}

def mean_tokens(rows):
    return round(sum(t['tokens_in'] + t['tokens_out'] for t in rows) / len(rows), 1)

R = {}
a1t = load('traces_mvr_A1T_run*.jsonl', phase='S2', arm='A1-T')
abl = {a: load(f'traces_abl_{a}_run*.jsonl', phase='S2') for a in ('A0', 'A1')}
s2_tasks = {t['qid'] for t in abl['A0']}
primary = s2_tasks - RECALL_CONTROL

R['design'] = {
    'arm': 'A1-T (store transplant, verifier off, Session 2 only)',
    'model': 'gpt-5-mini-2025-08-07',
    'trajectories_A1T_S2': len(a1t),
    'primary_tasks': len(primary),
    'comparators': 'A14 no-verifier A0/A1 traces reused (not re-run)',
}
R['levels'] = {
    'A1T_original': level(a1t, 'pass_original', primary),
    'A1T_corrected': level(a1t, 'pass_corrected', primary),
    'A0_noverifier_original': level(abl['A0'], 'pass_original', primary),
    'A1_noverifier_original': level(abl['A1'], 'pass_original', primary),
}
R['primary_contrast'] = {
    'A1T_minus_A0_noverifier_original': paired_diff(abl['A0'], a1t, 'pass_original', primary),
    'A1T_minus_A0_noverifier_corrected': paired_diff(abl['A0'], a1t, 'pass_corrected', primary),
}
R['secondary_contrast'] = {
    'A1T_minus_A1_noverifier_original': paired_diff(abl['A1'], a1t, 'pass_original', primary),
    'A1T_minus_A1_noverifier_corrected': paired_diff(abl['A1'], a1t, 'pass_corrected', primary),
}
# store sizes: start = verifier-on A1 S1 journal per run; shadow = A1-T S2 journal per run
store_sizes = {}
for run in (1, 2, 3, 4):
    rid = f'run{run}'
    src = [json.loads(l) for l in open(HF / f'episodes_stage1_A1_run{run}.jsonl')]
    start = sum(1 for e in src if e['arm'] == 'A1' and e['run_id'] == rid and e['phase'] == 'S1')
    sh_path = HF / f'episodes_mvr_A1T_run{run}.jsonl'
    shadow = 0
    if sh_path.exists():
        shadow = sum(1 for l in open(sh_path) if l.strip() and
                     json.loads(l)['phase'] == 'S2')
    store_sizes[rid] = {'store_size_S2_start': start,
                        'shadow_acquired_S2': shadow,
                        'store_size_S2_end': start + shadow}
R['store_sizes'] = store_sizes
rows_by_run = defaultdict(list)
for t in a1t:
    rows_by_run[t['run_id']].append(t)
R['retrieval'] = {
    'trajectories_with_retrieval': sum(1 for t in a1t if t['retrieved']),
    'trajectories_total': len(a1t),
    'episodes_retrieved_total': sum(len(t['retrieved']) for t in a1t),
    'per_run': {rid: {'with_retrieval': sum(1 for t in rs if t['retrieved']),
                      'total': len(rs),
                      'episodes_retrieved': sum(len(t['retrieved']) for t in rs)}
                for rid, rs in sorted(rows_by_run.items())},
}
R['tokens'] = {
    'A1T_mean_tokens_S2': mean_tokens(a1t),
    'A0_noverifier_mean_tokens_S2': mean_tokens(abl['A0']),
    'A1_noverifier_mean_tokens_S2': mean_tokens(abl['A1']),
}
acq = sum(t['acquired_episode'] for t in a1t)
unres = sum(t['unresolved_failure'] for t in a1t)
R['A1T_S2_shadow_acquisition'] = {'trajectories': len(a1t), 'episodes': acq,
                                  'unresolved': unres}
R['spend'] = json.load(open(HF / 'pilot_spend.json'))
json.dump(R, open(HF / 'mvr_a15.json', 'w'), indent=1)
print(json.dumps(R, indent=1))
