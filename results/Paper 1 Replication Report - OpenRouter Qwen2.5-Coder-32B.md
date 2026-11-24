# Paper #1 — Replication Report: OpenRouter Qwen2.5-Coder-32B-Instruct

## Correction note — 2026-11-24

Two statements in this report are corrected here. The body below is preserved unchanged as the as-run record.

1. **Silent-failure decomposition (Acquisition section).** The sentence "Of the 237 S1 failures, 123 were execution errors and 114 silent (accepted but wrong)" is **withdrawn**. The authoritative decomposition (from `pilot_rep_results.json`: 27 episodes acquired, 178 observed failures unresolved) is: 237 failed Session-1 trajectories = **205 agent-observed failures** (execution errors or verifier rejections) + **32 silent failures** (accepted but wrong, never observed by the agent). The acquisition rate is 27 / 205 = **0.132**. The related sentence in the same section — "A1 observed 237 failures across 400 trajectories and acquired only 27 verified episodes — acquisition rate 0.132" — pairs the correct rate with the wrong denominator: 237 counts all failed trajectories, including the 32 the agent never observed. (The printed "27 of 237" framing would give 0.114, not 0.132.)
2. **Decoding (Run status section).** The phrase "near-deterministic decoding at this model's default temperature" is **wrong**: the replication requests explicitly set **temperature 0** in the request body (harness code). It was the main study (gpt-5-mini) that sent no sampling parameters. A dated inline marker has been added at that sentence.

---


Date: 2026-11-22 (evening PT; completed ~23:30 PT). Protocol: Pilot Protocol v2 (frozen) + Amendments A4 (GO margin), A8 (staging), A9 (pivot), A12 (open-model replication via OpenRouter, superseding the Together route), A13 (A3 mercy rule). Model: **qwen/qwen-2.5-coder-32b-instruct** via OpenRouter. Analysis: `hidden_files/analysis_rep.py`, results in `hidden_files/pilot_rep_results.json`; traces in `hidden_files/traces_rep_*.jsonl` (12 files). Corrected-label contrasts use each trace's `pass_corrected` field and the 49 primary S2 tasks whose manifest `label_status` is L1 — the same definitions as the Stage 1/2 analyses.

## Run status — COMPLETE

Phase 1 (A0/A1, repeated split, 4 runs each) completed ~22:52 PT: all 1,600 trajectories. Phase 2 (A3, S2 only, 4 runs) completed ~23:02–23:30 PT: all 400 trajectories. All 12 workers ended with clean `DONE/STOPPED` log lines; no pilot workers remain alive and no worker needed relaunching by the watcher.

| Arm | Expected | Done | State |
|---|---|---|---|
| A0 (no memory, S1+S2) | 800 (200 × 4) | 800 | **Complete** |
| A1 (failure memory, S1+S2) | 800 (200 × 4) | 800 | **Complete** |
| A3 (generate-and-select, S2 only) | 400 (100 × 4) | 400 | **Complete** |

- Spend: **$2.37, 5,804 calls — inside the $10 replication cap** ($7.63 headroom). No spend-limit stall occurred (unlike the mini Stage 2 run).
- Total trajectories analysed: 2,000 (1,600 Phase 1 + 400 A3).
- Run-to-run variation is small: per-run S2 pass@1 (original labels) ranges 0.57–0.59 for every arm, consistent with near-deterministic decoding at this model's default temperature. [Correction, 2026-11-24: the replication requests explicitly set temperature 0; see correction note 2 at the top of this report.]

## Design fidelity

Same substrate (BIRD Dev, manifest_v2 frozen, Amendment M1 L3 relabelling of q1006 applied), same splits (100 repeated-failure pairs; 97 primary S2 tasks after excluding the 3 recall-control pairs 850/1326/1479), same prompts, same harness (`pilot.py`, `--backend openrouter`), same scoring (execution-accuracy result-set comparison, original and corrected labels), same 4 runs per task, same paired-bootstrap analysis (10,000 resamples, seed 20261122). Arms A0/A1/A3 are the same designs as the mini pilot; A2 and drift were not replicated (out of the A12 scope).

Two deliberate differences from the mini run, both recorded in amendments:

1. **A3 cap enforced over the whole trajectory (Amendment A10 fix).** The cap is A1's measured mean S2 tokens in *this* replication — **1,614 tokens** (`hidden_files/rep_a3_cap.txt`), vs 3,506 for mini — and the harness's `_budgeted_call` now caps every call, selector included, so the trajectory cannot overshoot. Mini A3 overshot its cap by 17% (mean 4,102 vs 3,506) because the selector call sat outside the cap check; the replication closes that hole. The consequence, documented below, is that the cap now *truncates* A3 instead.
2. **A3 mercy rule (Amendment A13).** The pre-call token estimator blocked even the first candidate on large-schema tasks; the harness allows exactly one capped call (max_tokens=384) so the arm always produces a candidate, flagged `cap_mercy` in the trace.

## Primary result — the A1 null replicates exactly

Paired pass@1, Session-2, 97 primary tasks (recall-control excluded), original labels:

| Contrast | Pass@1 | Diff (95% CI) |
|---|---|---|
| A1 vs A0 | 0.583 vs 0.583 | **0.000 (−0.046 … +0.046)** |
| A3 vs A0 | 0.590 vs 0.583 | +0.008 (−0.064 … +0.083) |
| A3 vs A1 | 0.590 vs 0.583 | +0.008 (−0.080 … +0.095) |

- **Failure memory is null on a second model, with a point estimate of exactly zero.** A1 and A0 both score 0.583; the CI (±4.6 points) is slightly tighter than mini's (±~4 points around −1.8) and rules out any gain larger than ≈5 points. The pre-committed +12-point GO margin fails again.
- **A3 is also null here** — but see the cap caveat below before reading this as a refutation of mini's A3 win.
- On the 49 corrected-label tasks: A0 0.454, A1 0.485, A3 0.495. Contrasts: A1−A0 **+0.031 (0.000 … +0.082)** — the interval touches zero at its lower end, not a significant effect; A3−A0 +0.041 (−0.041 … +0.122); A3−A1 +0.010 (−0.082 … +0.102). No corrected-label contrast is significant in either direction.

## Acquisition — the Qwen store was thin (a caveat on the A1 null)

In Session 1, A1 observed 237 failures across 400 trajectories and acquired only **27 verified episodes — acquisition rate 0.132**, against mini's 0.565 (100 episodes, 77 unresolved). The store A1 drew on in Session 2 was therefore much thinner, and the replication's A1 null has a different texture from mini's: mini's null is "memory, well stocked, did not help"; Qwen's null is partly "memory, thinly stocked, did not help."

Why so thin: Qwen rarely produced an execution-verified remediation. Of the 237 S1 failures, 123 were execution errors and 114 silent (accepted but wrong); only 15 of the 237 failures yielded an episode, with 12 further episodes coming from trajectories that failed, were repaired, and ultimately passed. A contributing mechanism is visible in the traces: in 22% of multi-attempt S1 trajectories the agent resubmitted byte-identical SQL after error feedback (the F9 no-change repair loop — present here, though far below the 3B local model's 8/8). Retrieval in Session 2 still happened (184/400 trajectories retrieved ≥1 episode), and pass@1 was 0.560 with retrieval vs 0.588 without — no benefit signal from the episodes that were retrieved.

This does not overturn the replication's headline — the A1 point estimate is exactly zero with a tight CI — but the paper should report the acquisition contrast honestly: the two models' nulls were reached with very different store densities, and a Qwen run with a denser store is a conceivable (if not evidently promising) follow-up.

## A3 — the enforced cap truncated generate-and-select

A3 mean cost is **1,340 tokens/trajectory** (1.54 attempts) — *under* its 1,614 cap, not over it. That is not because the procedure is cheap; it is because the whole-trajectory cap blocked calls:

- **356/400 trajectories (89%) hit `cap_fallback`** — a candidate-generation call or the selector call was refused for budget, and the arm fell back to the first executable candidate.
- Candidate counts: only **72/400 trajectories got the full 3 candidates**; 256 got 1 candidate and 72 got 2.
- **88/400 (22%) hit `cap_mercy`** — the estimator blocked even the first candidate, and the single capped mercy call produced the only candidate.

So the replication's A3 is a *truncated* generate-and-select (usually one candidate, usually no selection), whereas mini's A3 ran the full 3-candidate procedure with a selector — at 17% over its nominal budget. The two A3 results are therefore not the same arm under the same budget: mini bought the full procedure with extra tokens; the replication bought a truncated procedure within budget. The replication's A3 null (+0.8 points) cannot be read as a clean refutation of mini's original-label A3 win (+9.8), and mini's win cannot be read as a token-matched result. Both A3 numbers stay as-run, with their opposite caveats. A genuinely token-matched A3 would need a procedure designed to fit the budget (e.g. fewer, cheaper candidates), not a cap bolted onto a procedure that costs more than the budget.

## Comparison with the gpt-5-mini primary results

| Contrast (original labels, 97 primary tasks) | gpt-5-mini | Qwen2.5-Coder-32B (OpenRouter) |
|---|---|---|
| A0 pass@1 | 0.539 | 0.583 |
| A1 pass@1 | 0.521 | 0.583 |
| A3 pass@1 | 0.637 | 0.590 |
| A1 − A0 | −0.018 (−0.057 … +0.021) | **0.000 (−0.046 … +0.046)** |
| A3 − A0 | +0.098 (+0.041 … +0.160) | +0.008 (−0.064 … +0.083) |
| A3 − A1 | +0.116 (+0.057 … +0.180) | +0.008 (−0.080 … +0.095) |
| A1 acquisition rate | 0.565 | 0.132 |
| A1 mean S2 tokens | 3,506 | 1,614 |
| A3 mean S2 tokens (cap) | 4,102 (cap 3,506, +17% overshoot) | 1,340 (cap 1,614, enforced) |

What replicates, what does not:

1. **The failure-memory null replicates.** Two models, two token regimes, two acquisition rates — A1−A0 is −1.8 and 0.0 points, both CIs including zero, both far below the +12 GO margin. This is the replication's main contribution to the paper: the negative result is not a single-model artefact.
2. **The A3 original-label win does not replicate** — but the non-replication is confounded by the cap change above: mini's A3 was full-procedure/over-budget, the replication's was truncated/within-budget. The corrected-label A3 contrast is null in both models (mini 0.000, replication +0.041), so the label-sensitivity point — the win does not survive audited labels — is consistent across models.
3. **Base rates differ.** Qwen's no-memory baseline (0.583) is ~4 points above mini's (0.539) on the same tasks, and Qwen is ~2× cheaper per trajectory (A1 1,614 vs 3,506 tokens). Model identity moves the level; it does not move the memory contrast.

## Verdict

**The pivot (Amendment A9) stands and is now two-model evidence.** The replication adds a second, independent null for failure memory at matched compute, with an exactly-zero point estimate — the strongest single number in the study for the claim that failure memory does not help this agent. It also sharpens the A3 story in both directions: the original-label win is model- and procedure-sensitive, and a whole-trajectory cap that actually binds truncates generate-and-select rather than matching it. Draft v1 §5 gains a replication subsection and §7's single-model limitation is retired (the single-benchmark limitation remains).

## Recommended next steps (author decision)

1. **Replication is complete — no resume needed.** All arms finished inside the $10 cap ($2.37 spent, $7.63 headroom). The remaining headroom does not fund a meaningful new arm; any further runs (A2/drift on Qwen, a budget-fitting A3 redesign) need a fresh budget decision.
2. If A3 is ever re-tested at matched compute, redesign the procedure to fit the budget (e.g. 2 candidates with a cheap selector) rather than capping a 3-candidate procedure that costs more than the budget — the current pair of A3 results shows both failure modes of the bolt-on cap.
3. **Draft Paper #1 under the pivot framing with two-model evidence.** The replication results are incorporated into Draft v1 (§5.5, §7); the watcher cron for this replication is removed on completion.
