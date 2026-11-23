# Paper #1 — Pilot Stage 1 Report (A0 vs A1, repeated-failure split)

Date: 2026-11-22. Protocol: Pilot Protocol v2 (frozen) + Amendments A4 (GO margin) and A8 (staging). Model: gpt-5-mini-2025-08-07 (pinned snapshot) via OpenAI. Analysis: `hidden_files/analysis_stage1.py`, results in `hidden_files/pilot_stage1_results.json`; traces in `hidden_files/traces_stage1_*.jsonl` (8 files).

## Design as run
- Arms: A0 (no memory) vs A1 (fingerprint-keyed episodic failure memory, raw traces, no LLM consolidation; acquisition per Protocol §6 — episodes only from agent-discovered, execution-verified remediations; gold never used).
- Repeated-failure split: 100 Session-1/Session-2 pairs × 4 runs × 2 arms = 1,600 trajectories, all completed. Primary metric: paired pass@1 on Session-2 tasks, original labels, recall-control pairs (distance < 0.10) excluded → **97 primary tasks**.
- Total mini-effort spend: **$6.13** of the $10 cap (Amendment A8); 4,295+ API calls. No budget or credit stop occurred.

## Primary result — NO GAIN
| Arm | Pass@1 (97 primary S2 tasks) |
|---|---|
| A0 no memory | 0.539 |
| A1 failure memory | 0.521 |
| **Paired difference (A1 − A0)** | **−0.018 (95% CI −0.057 … +0.021)** |

- GO check (Amendment A4: ≥ +12 points AND CI excludes 0): **FAIL** — by a wide margin. The confidence interval rules out any true gain larger than ≈ +2 points in this regime; this is an informative null, not merely an underpowered one.
- Corrected-label subset (49 primary tasks with Jin L1 labels): paired difference −0.010 (CI −0.061 … +0.041). Same conclusion on audited labels.
- Distance strata (paired diff by Session-1↔2 similarity tertile): near −0.038 (n=33), mid +0.008 (n=32), far −0.023 (n=32). No stratum shows a gain; the null is not hiding in the most-similar pairs.

## Acquisition — the memory was real
- A1 Session-1: 400 trajectories; 177 observed failures; **100 episodes acquired (acquisition rate 0.565)**, 77 failures unresolved (logged separately per §6).
- The null result is therefore NOT explained by an empty or near-empty store: memory had substantial, verified content and was retrieved in Session 2 — and did not help.

## Fairness / cost tables (Session-2, per trajectory)
| Arm | Mean tokens | Mean attempts | Mean latency |
|---|---|---|---|
| A0 | 2,862 | 1.68 | 22.4 s |
| A1 | 3,506 (+22%) | 1.69 | 23.7 s |

At essentially identical attempt counts, A1 spent ~22% more tokens (the injected memory context) for −1.8 points. On a token-matched view the comparison is worse for A1, not better.

## Verdict under the frozen rules (Protocol §9)
**PIVOT.** The pre-committed rule applies: memory shows no pilot gain, so Paper #1 pivots to the compute-fair / corrected-label negative-result paper (gaps G2 + G5), rather than a memory-method paper. The frozen claim in Protocol §1 is not edited and is not quietly replaced; it is reported as tested and not supported in this regime.

## What this result does and does not establish
Established (this regime: gpt-5-mini, BIRD repeated-failure pairs at median structural distance 0.209, raw episodic memory with fingerprint+embedding retrieval):
- No pass@1 benefit from failure memory; any benefit is < ~2 points.
- The result survives corrected labels and holds across similarity strata.
- Memory acquisition at 56.5% is feasible under a strict no-gold policy — a reusable methodological finding for the pivot paper.

Not established:
- Anything about drift / stale memory (A4 arm, drift split — Stage 2, not run).
- Anything about generate-and-select at matched compute (A3 — Stage 2, not run) or generic vs fingerprinted memory (A2 — not run).
- Other models or benchmarks; a stronger model with different failure mix could behave differently.
- Mechanisms: candidate explanations (retrieved episodes acting as distractors; S2 failures dominated by classes memory cannot fix, e.g. F7 answer-shape; pair similarity too low for transfer) are hypotheses for the paper's discussion, not findings of this pilot.

## Recommended next steps (author decision)
1. Adopt the §9 pivot as Paper #1's framing: a compute-fair, corrected-label evaluation study whose headline is this null result plus the acquisition methodology.
2. Decide whether Stage 2 still runs: A3 (generate-and-select at matched tokens) would directly strengthen the pivot paper's compute-fairness claim (G2); A2/A4/drift would bound the null's scope. Each needs its own budget decision; Stage 1's measured rates (≈ $0.0037/trajectory) price them precisely.
3. If the pivot is adopted, begin drafting Paper #1 (methods + results from the frozen record) without waiting for Stage 2.
