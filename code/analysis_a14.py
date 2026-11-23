#!/usr/bin/env python3
"""Amendment A14 analyses: F1 paired drift effect + verifier ablation.
Paired per-task run-mean pass@1 differences, task-level bootstrap 95% CIs,
seed 20261122 (same method as analysis_stage1/2). Output: a14_results.json.
"""
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
    """b minus a, paired by task, bootstrap CI."""
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

R = {}

# ---------- F1: paired drift effect (A0, same 60 tasks) ----------
a0_drift = load('traces_stage2_drift_run*.jsonl', phase='drift', arm='A0')
a0_undrift = load('traces_fix_ctrl_run*.jsonl', phase='undrifted', arm='A0')
R['F1'] = {
    'undrifted_level_original': level(a0_undrift, 'pass_original'),
    'undrifted_level_corrected': level(a0_undrift, 'pass_corrected'),
    'drifted_level_original': level(a0_drift, 'pass_original'),
    'drifted_level_corrected': level(a0_drift, 'pass_corrected'),
    'paired_drift_effect_original': paired_diff(a0_undrift, a0_drift, 'pass_original'),
    'paired_drift_effect_corrected': paired_diff(a0_undrift, a0_drift, 'pass_corrected'),
}

# ---------- Ablation: verifier off vs on (repeated split) ----------
abl = {a: load(f'traces_abl_{a}_run*.jsonl', phase='S2') for a in ('A0', 'A1')}
on = {a: load(f'traces_stage1_{a}_run*.jsonl', phase='S2') for a in ('A0', 'A1')}
s2_tasks = {t['qid'] for t in on['A0']}
primary = s2_tasks - RECALL_CONTROL
R['ablation'] = {
    'A1_minus_A0_noverifier_original': paired_diff(abl['A0'], abl['A1'], 'pass_original', primary),
    'A1_minus_A0_noverifier_corrected': paired_diff(abl['A0'], abl['A1'], 'pass_corrected', primary),
    'A0_level_noverifier': level(abl['A0'], 'pass_original', primary),
    'A1_level_noverifier': level(abl['A1'], 'pass_original', primary),
    'A0_verifier_effect_on_minus_off': paired_diff(abl['A0'], on['A0'], 'pass_original', primary),
    'A1_verifier_effect_on_minus_off': paired_diff(abl['A1'], on['A1'], 'pass_original', primary),
}
abl_s1 = load('traces_abl_A1_run*.jsonl', phase='S1')
eps = sum(t['acquired_episode'] for t in abl_s1)
unres = sum(t['unresolved_failure'] for t in abl_s1)
R['ablation']['A1_acquisition_noverifier'] = {
    's1_trajectories': len(abl_s1), 'episodes': eps, 'unresolved': unres,
    'rate': round(eps / (eps + unres), 4) if (eps + unres) else None}
for a in ('A0', 'A1'):
    rows = abl[a]
    R['ablation'][f'{a}_mean_tokens_S2_noverifier'] = round(
        sum(t['tokens_in'] + t['tokens_out'] for t in rows) / len(rows), 1)

R['spend'] = json.load(open(HF / 'pilot_spend.json'))
json.dump(R, open(HF / 'a14_results.json', 'w'), indent=1)
print(json.dumps(R, indent=1))
