# Paper #1 — Pilot Power Analysis (Protocol §8 output)

Date: 2026-11-22. Script: `hidden_files/power_analysis.py` (seed 20261122); raw output: `hidden_files/power_analysis_out.txt`. Uses ONLY A0 dry-run base rates, per Protocol §8 — no arm results exist yet.

## Inputs (A0 dry runs, same 11 tasks)
- GPT-5 (pinned gpt-5-2025-08-07, primary model): 5/11 = 0.45 on original labels; 6/11 = 0.55 on Jin corrected labels.
- Qwen2.5-Coder 3B (local reference only, not a pilot model): 5/11 = 0.45.
- Sensitivity range simulated: p0 ∈ {0.30, 0.45, 0.55}. The 0.30 row matters because the repeated-failure split is failure-selected, which depresses the A0 rate relative to a random sample; n=11 intervals are wide, so the design must not hinge on the point estimate.

## Designs simulated (cross-check)
- **Design A (primary — matches the §8 analysis plan):** per-task latent success prob (Beta, mean p0); A1 prob shifted so the marginal gain is Δ; 4 runs per arm per task; paired t-test (α=0.05, two-sided) on per-task mean pass@1 differences. 10,000 sims/cell.
- **Design B (conservative cross-check):** single-run-equivalent paired Bernoulli, McNemar exact test, harm share (A0-pass→A1-fail fraction of discordance) 0.25 and 0.10. This discards the variance reduction from 4-run averaging, so it lower-bounds power. 5,000 sims/cell.

## Results — Design A power (probability of detecting a true paired gain Δ)
| p0 | n | Δ=0.10 | Δ=0.15 | Δ=0.20 | MDE @80% power |
|----|---|--------|--------|--------|----------------|
| 0.30 | 60 | 0.59 | 0.90 | 0.99 | 0.15 |
| 0.30 | 100 | 0.81 | 0.99 | 1.00 | 0.10 |
| 0.45 | 60 | 0.55 | 0.89 | 0.99 | 0.15 |
| 0.45 | 100 | 0.78 | 0.98 | 1.00 | 0.12 |
| 0.45 | 160 | 0.93 | 1.00 | 1.00 | 0.10 |
| 0.55 | 60 | 0.58 | 0.90 | 0.99 | 0.15 |
| 0.55 | 100 | 0.78 | 0.99 | 1.00 | 0.12 |

Design B (McNemar, harm share 0.25): n=60 → power 0.30 / 0.50 / 0.64 at Δ = 0.10 / 0.15 / 0.20; n=100 → 0.55 / 0.75 / 0.88. With harm share 0.10, n=100 → 0.79 / 0.95 / 0.99. The gap between designs is the value of the pre-committed 4-run averaging; the pilot analysis must use run-mean pass@1 as specified, not single runs.

Key robustness finding: **Design A power is nearly invariant to the base rate** across p0 ∈ [0.30, 0.55] (MDE at n=60 is 0.15 in every row). One GO margin therefore serves both pilot models despite the second model's unknown A0 rate (Amendment A2's per-model concern is answered by this invariance; recorded in Amendment A4).

## Decisions (recorded as Protocol Amendment A4)
1. **Split sizes (final, per §6's delegation to §8):** repeated-failure split **100 tasks** (raised from ~60); drift split **60 tasks** (raised from ~40; its contrasts remain secondary — MDE ≈ 0.15 at n=60). Total pilot pool: 160 tasks.
2. **GO margin: 12 percentage points** paired pass@1 (A1 − A0) on the repeated-failure split, with the paired 95% CI excluding 0 (both §9 conditions). At n=100 this gives ≈90% power for a true 12-point effect at the observed base rates, ≈98% at 15 points, ≈78–81% at 10 points.
3. Honest limits, to be stated in the paper's methods: the pilot is underpowered for true effects below ~10 points; a null pilot result rules out large memory gains, not small ones — which is exactly what the §9 pivot (compute-fair negative-result paper) is designed to publish.

## Cost note (for the separate pilot-budget decision)
At dry-run observed GPT-5 prices (~$0.008 per single-attempt task-run; memory arms carry retrieval context, est. 2–3×), the full pilot (160 tasks × 4 runs × applicable arms) estimates at roughly **$25–60**. This exceeds the current $5 budget (Amendment A3); split construction itself is local work and costs nothing. No pilot run may start until the author sets a pilot budget.
