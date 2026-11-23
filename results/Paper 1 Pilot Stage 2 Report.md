# Paper #1 — Pilot Stage 2 Report (A3 / A2 / drift)

Date: 2026-11-22 (evening PT). Protocol: Pilot Protocol v2 (frozen) + Amendments A4 (GO margin), A8 (staging), A9 (pivot + Stage 2 scope and $10 Stage 2 cap, $16.13 total mini-effort cap). Model: gpt-5-mini-2025-08-07 (pinned snapshot) via OpenAI. Analysis: `hidden_files/analysis_stage2.py`, results in `hidden_files/pilot_stage2_results.json` (final run, 2026-11-23 ~05:30 UTC); traces in `hidden_files/traces_stage2_*.jsonl`. Corrected-label A2/A3 and drift contrasts were computed with the same paired-bootstrap method as `analysis_stage2.py` (seed 20261122), using each trace's `pass_corrected` field and the 49 primary S2 tasks whose manifest `label_status` is L1.

## Run status — COMPLETE

Stage 2 launched 2026-11-22 evening as 12 workers (A3×4, A2×4, drift×4). It **stalled at ~19:39 PT on the OpenAI project enforced spend limit** (429 `project_spend_limit_exceeded`; see the correction section below), was **resumed ~20:03 PT** after Mohan raised the project monthly spend limit to $25, and **finished ~21:22 PT**: all 8 resumed workers ended with clean `DONE/STOPPED` log lines and no pilot workers remain alive.

| Arm | Expected | Done | State |
|---|---|---|---|
| A3 (generate-and-select, S2 only) | 400 (100 × 4 runs) | 400 | **Complete** |
| A2 (generic memory, S1+S2) | 800 (200 × 4) | 800 | **Complete** — S1 400/400, S2 400/400 |
| Drift (A4 pre + A0/A1/A4 drift) | 960 (240 × 4) | 960 | **Complete** — A4 pre 240/240; drift phase A0/A1/A4 180 × 4 |

- Spend: **$14.91 total mini effort** (Stage 1 $6.13 + Stage 2 $8.78), 10,762 calls — **inside the $16.13 cap** ($1.22 headroom remaining). The OpenAI project monthly limit ($25, set at resume) was not reached either; the final ledger is the pilot-side total.
- Total trajectories analysed: 2,800 repeated-split (Stage 1 + Stage 2) and 960 drift.

## Stall and resume history (2026-11-22 evening)

- **Stall ~19:39 PT.** All 8 A2/drift workers stopped on OpenAI 429 `project_spend_limit_exceeded` — the project's configured enforced spend limit, not a transient helper/network fault and not the pilot's $16.13 cap (spend then was $11.20). The workers exited cleanly through the harness's error path (`STOPPED (API)` … `DONE/STOPPED. ledger: {'mini_usd': 11.1976, 'calls': 8330}`). A resume attempt at ~19:53 PT failed instantly on the same 429; a models-list probe still succeeded, so only chat completions were blocked.
- **Unblock.** Mohan signed in (OpenAI account moganakumaran@gmail.com) and raised the project monthly spend limit to $25 (page showed $11.07/$25.00). The original pre-stall limit was never observed — do not state it.
- **Resume ~20:03 PT, finish ~21:22 PT.** The harness resumed from existing traces + the episodes journal (validated in Stage 1): A2 S2 picked up from ~85/400, drift from A0 ~163/240, then A1/A4 drift. Resume cost was ~$3.71 (from $11.20 to $14.91), close to the ~$3.40 estimate. No worker was relaunched by the watcher (hard constraint); the resume was a fresh launch by the main agent.

## Primary result — A3 (generate-and-select)

Paired pass@1, Session-2, 97 primary tasks (recall-control excluded), original labels:

| Contrast | Pass@1 | Diff (95% CI) |
|---|---|---|
| A3 vs A0 | 0.637 vs 0.539 | **+0.098 (+0.041 … +0.160)** |
| A3 vs A1 | 0.637 vs 0.521 | **+0.116 (+0.057 … +0.180)** |

- On original labels, generate-and-select beats both no-memory and failure-memory, and both CIs exclude 0. This is the first positive arm result in the pilot.
- **But it does not survive corrected-label scoring.** On the 49 primary tasks with Jin L1 corrected labels: A3 vs A0 diff **0.000 (CI −0.082 … +0.082)**; A3 vs A1 **+0.010 (CI −0.077 … +0.102)**. Two readings are both live: (a) the original-label win is a label-noise artefact (A3 matching buggy golds more often); (b) the 49-task subset is underpowered (±8 pts) and cannot exclude a real effect of that size. The data as they stand cannot distinguish these. Both label views must be reported in the paper; the A3 win cannot be claimed unconditionally.
- **Token-match caveat.** A3 mean cost is **4,102 tokens/trajectory** (median 4,182; range 1,738–7,332; mean 2.86 attempts) vs A1 3,506 and A0 2,862 — i.e. **+17% over A1's mean and +43% over A0**. The cap (3,506) is enforced only before each candidate-generation call; the selector call is uncapped, so A3 systematically overshoots the nominal matched budget. "Matched tokens" is approximate, not exact, and the A3-vs-A1 comparison is not a clean equal-compute contrast. Any paper claim must state the measured +17% overshoot.

## A2 (generic memory) — null on both label views

Paired pass@1, Session-2, 97 primary tasks (recall-control excluded), 4 runs per task:

| Contrast | Pass@1 | Diff (95% CI) | Corrected-label diff (49 L1 tasks, 95% CI) |
|---|---|---|---|
| A2 vs A0 | 0.492 vs 0.539 | **−0.046 (−0.095 … 0.000)** | −0.046 (−0.107 … +0.010) |
| A2 vs A1 | 0.492 vs 0.521 | **−0.028 (−0.077 … +0.016)** | −0.036 (−0.077 … +0.005) |

- Generic (unfingerprinted) memory is **also null**: A2 is below both no-memory and failure-memory on both label views, with both CIs including 0 (the A2-vs-A0 original-label CI just touches 0 at its upper end). The completed data reverse the partial-run hint, which had A2 vs A1 slightly positive on 22 tasks — that was a small, non-representative subset (the first ~21 S2 tasks in manifest order).
- **Token-matched, unlike A3.** A2 mean cost is 3,463 tokens/trajectory (1.70 attempts) vs A1 3,506 and A0 2,862 — so the A2 null is a clean equal-compute null, not a budget artefact. Together with the Stage 1 A1 null, this says: neither failure-memory nor generic memory helps this agent at equal compute on repeated failures.
- Implication for the paper: the negative result generalises across memory designs (fingerprinted A1 and generic A2), which strengthens the pivot paper's claim that the failure-memory benefit reported in the literature does not survive a compute-fair, paired test on this substrate.

## Drift / stale memory — answered: stale memory does NOT hurt, live memory does NOT help

Paired pass@1 on the drift phase, 60 tasks × 4 runs (A4 pre-drift stores built before drift; A0/A1/A4 all run on the drifted databases):

| Contrast | Pass@1 | Diff (95% CI) | Corrected-label diff (95% CI) |
|---|---|---|---|
| A1 − A0 (live memory) | 0.263 vs 0.308 | −0.046 (−0.096 … +0.004) | −0.008 (−0.050 … +0.033) |
| A4 − A0 (stale memory) | 0.292 vs 0.308 | −0.017 (−0.063 … +0.029) | +0.013 (−0.029 … +0.054) |
| A4 − A1 (stale vs live) | 0.292 vs 0.263 | +0.029 (−0.021 … +0.079) | +0.021 (−0.017 … +0.067) |

Split by drift type (original labels):

| Contrast | Silent drift (33 tasks) | Overt drift (27 tasks) |
|---|---|---|
| A1 − A0 | −0.038 (−0.083 … 0.000) | −0.056 (−0.157 … +0.046) |
| A4 − A0 | 0.000 (−0.053 … +0.046) | −0.037 (−0.120 … +0.046) |

- **Stale memory does not hurt.** A4 (episodes acquired pre-drift, applied to drifted databases) is within ±2 pts of no-memory overall, and exactly 0.000 on the 33 silent-drift tasks — the split where stale memory was hypothesised to hurt most. Every CI includes 0.
- **Live memory does not help under drift either.** A1 is below A0 on both drift types and both label views; the original-label A1−A0 CI (−0.096 … +0.004) nearly excludes 0 in the negative direction, but the corrected-label view (−0.008) pulls it back to null — another label-sensitivity signal.
- **Drift itself is the dominant effect.** A0 on drifted databases: pass@1 **0.308**, vs 0.539 on the same arm's non-drifted S2 — drift roughly halves pass@1, as expected. Silent drift (A0 0.326) is only slightly easier than overt drift (A0 0.287).
- Caveat: 60 drift tasks is small; CIs are ±5–12 pts, so a small stale-memory harm (a few points) cannot be excluded. But the hypothesised direction — stale memory actively misleading the agent under silent drift — is not observed: the point estimate on silent drift is exactly zero.

## Verdict under the frozen rules (Protocol §9, Amendment A9)

**Pivot stands — and is now stronger.** The Stage 1 null (A1 memory: −1.8 pts) is untouched, and Stage 2 adds two further nulls: generic memory (A2) is null on both label views, and neither live nor stale memory moves pass@1 under drift. The one positive Stage 2 signal (A3 on original labels) fails the corrected-label check the paper itself treats as the validity standard. Stage 2 therefore does **not** overturn the pivot to the compute-fair / corrected-label negative-result paper (G2 + G5). What Stage 2 adds to that paper:

1. A qualified, label-sensitive A3 finding: generate-and-select looks strong on noisy labels and null on audited labels — direct evidence for the paper's G2/G5 argument that unevaluated label noise and unmatched compute can manufacture apparent method wins.
2. The token-overshoot finding: a nominally "matched" arm exceeded its cap by 17% because the selector call sat outside the cap check — a concrete compute-fairness failure mode to report, and a fix (cap the whole trajectory) for any resumed run.
3. A completed drift experiment: stale memory does not hurt (A4−A0 ≈ 0, exactly 0 on silent drift), live memory does not help under drift, and drift itself halves pass@1. This closes the stale-memory question the partial report left open — it is a null, not a hazard, at this sample size.
4. A second, cleanly token-matched null (A2): the negative result now spans two memory designs, so it cannot be dismissed as an artefact of fingerprinting specifically.

## Recommended next steps (author decision)

1. **Stage 2 is complete — no resume needed.** All three arms finished within the $16.13 cap ($14.91 spent, $1.22 headroom). The remaining headroom does not fund a meaningful new arm; any further runs (e.g. a token-capped A3 re-run, an open-model slot) need a fresh budget decision.
2. If an A3 re-run is ever commissioned, fix the cap to cover the whole trajectory (including the selector call) so the comparison is genuinely token-matched; the current A3 numbers stay as-run and are reported with the +17% overshoot.
3. **Draft Paper #1 under the pivot framing.** All Stage 2 results are final as-run: the A1 null, the A2 null, the A3 label-sensitivity result, the drift nulls, the acquisition methodology, and the token-overshoot finding.
