#!/usr/bin/env python3
"""Paper #1 pilot — simulation-based power analysis (Protocol Section 8, Amendment A2).
Inputs: ONLY A0 dry-run base rates (no arm results exist yet).
- GPT-5 (primary model) A0: 5/11 = 0.45 original labels; 6/11 = 0.55 corrected labels.
- Qwen2.5-Coder 3B A0: 5/11 = 0.45 original labels.
The pilot primary metric (Protocol S8): paired pass@1 difference (A1 vs A0) on the
repeated-failure split, pass@1 = mean per-run success over 4 runs/task, paired by task.

Two simulation designs, cross-checked:
(A) Run-level: per task, latent A0 success prob theta ~ Beta(mean=p0, moderate spread);
    A1 prob = clip(theta + shift) with shift calibrated so marginal A1 rate = p0 + delta.
    4 runs per arm per task; test = paired t-test (normal approx, alpha=0.05 two-sided)
    on per-task mean differences. Matches the S8 analysis plan.
(B) Conservative cross-check: single-run-equivalent paired Bernoulli (McNemar exact test)
    parameterised by discordant rates u=P(A0 fail,A1 pass), v=P(A0 pass,A1 fail),
    delta = u - v, harm share v/(u+v) in {0.1, 0.25}.

Grid: p0 in {0.30 (failure-selected split depresses A0), 0.45 (dry-run), 0.55 (corrected)},
delta in {0.05..0.30}, n in {60 (planned repeated-failure split), 100, 160}.
10,000 sims per cell (design A), 5,000 (design B). Seed fixed for reproducibility.
"""
import random, math
from math import comb

random.seed(20261122)
SIMS_A, SIMS_B = 10000, 5000
RUNS = 4

def beta_params(mean, kappa=8.0):
    return mean * kappa, (1 - mean) * kappa

def sim_A(p0, delta, n, sims=SIMS_A):
    a, b = beta_params(p0)
    hits = 0
    for _ in range(sims):
        diffs = []
        for _i in range(n):
            theta = random.betavariate(a, b)
            # calibrate shift per task population: use fixed shift s.t. E[clip] approx p0+delta
            theta1 = min(1.0, max(0.0, theta + delta * 0.9))  # slight clip attenuation, conservative
            x0 = sum(1 for _ in range(RUNS) if random.random() < theta) / RUNS
            x1 = sum(1 for _ in range(RUNS) if random.random() < theta1) / RUNS
            diffs.append(x1 - x0)
        m = sum(diffs) / n
        var = sum((d - m) ** 2 for d in diffs) / (n - 1)
        if var <= 0:
            continue
        t = m / math.sqrt(var / n)
        if abs(t) > 1.96 and m > 0:
            hits += 1
    return hits / sims

def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)

def sim_B(p0, delta, n, harm_share=0.25, sims=SIMS_B):
    disc = delta / (1 - 2 * harm_share) if harm_share < 0.5 else delta
    u = disc * (1 - harm_share)   # A0 fail -> A1 pass
    v = disc * harm_share         # A0 pass -> A1 fail
    p_both_pass = p0 - v
    p_both_fail = 1 - p0 - u
    if p_both_pass < 0 or p_both_fail < 0:
        return None
    hits = 0
    for _ in range(sims):
        b = c = 0
        for _i in range(n):
            r = random.random()
            if r < v:
                c += 1
            elif r < v + u:
                b += 1
        if b + c > 0 and mcnemar_exact_p(b, c) < 0.05 and b > c:
            hits += 1
    return hits / sims

def mde(fn, p0, n, target=0.80, **kw):
    prev = 0.0
    for d in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]:
        pw = fn(p0, d, n, **kw)
        if pw is not None and pw >= target:
            return d, pw
        prev = d
    return None, pw

print("=== Design A (run-level, paired t on task means, 4 runs/task) ===")
for p0 in (0.30, 0.45, 0.55):
    for n in (60, 100, 160):
        row = {d: sim_A(p0, d, n) for d in (0.10, 0.15, 0.20)}
        d_mde, pw = mde(sim_A, p0, n)
        print(f"p0={p0} n={n}: power@.10={row[0.10]:.2f} @.15={row[0.15]:.2f} @.20={row[0.20]:.2f} | MDE(80%)={d_mde} (power {pw:.2f})" if pw else
              f"p0={p0} n={n}: power@.10={row[0.10]:.2f} @.15={row[0.15]:.2f} @.20={row[0.20]:.2f} | MDE(80%) > 0.30")

print("\n=== Design B (McNemar exact, single-run equivalent, harm share 0.25) ===")
for p0 in (0.30, 0.45, 0.55):
    for n in (60, 100):
        row = {d: sim_B(p0, d, n) for d in (0.10, 0.15, 0.20)}
        print(f"p0={p0} n={n}: power@.10={row[0.10]} @.15={row[0.15]} @.20={row[0.20]}")
print("\n=== Design B (harm share 0.10) ===")
for p0 in (0.45,):
    for n in (60, 100):
        row = {d: sim_B(p0, d, n, harm_share=0.10) for d in (0.10, 0.15, 0.20)}
        print(f"p0={p0} n={n}: power@.10={row[0.10]} @.15={row[0.15]} @.20={row[0.20]}")
