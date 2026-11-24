# B-02 memo — the missing cell: original-label contrasts on the corrected subset (2026-11-24)

**Question (logical review B-02).** Paper #1 reports A3−A0 = +9.8 pts on
original labels over the 97 primary tasks and A3−A0 = 0.0 on corrected
labels over the 49-task corrected (L1) subset. Two things change between
those numbers — the label view and the task set — and the original-label
contrast restricted to the same 49 tasks was never reported, so the
"label flip" attribution was confounded by subset composition.

**Method.** `analysis_b02_subset.py`, stored Stage 1/2 traces only, no
model calls. Estimator identical to `analysis_stage2.py` (paired per-task
run-mean pass@1, task-level bootstrap 95% CI, 10,000 resamples);
`random.seed(20261122)` reset per contrast (the `mvr_analysis5`
convention). Corrected subset = primary tasks with an L1 corrected label
in `manifest_v2.csv` (n = 49; qids in `b02_subset_results.json`).

**Validation gate (passed before any new number was used).**
- A3−A0 original, 97 tasks: +0.0979, CI [+0.0412, +0.1598] — reproduces
  `pilot_stage2_results.json` exactly.
- A3−A0 corrected, 49 tasks: 0.0, CI [−0.0816, +0.0816] — reproduces
  `mvr_analysis5.json` (`mini_A3-A0_corrected`) exactly.

**The missing cell.** On ORIGINAL labels restricted to the same 49 tasks:

| Contrast (n = 49, original labels) | Diff (pts) | 95% CI |
|---|---|---|
| A3−A0 | **+10.2** | +1.5 … +19.9 |
| A3−A1 | +11.2 | +2.0 … +21.4 |
| A1−A0 | −1.0 | −5.1 … +3.1 |
| A2−A0 | −2.6 | −7.7 … +2.0 |

Levels on the 49, original labels: A3 pass@1 = 0.5816, A0 = 0.4796
(corrected labels, same tasks: both 0.6071).

**Decomposition of the +9.8 → 0.0 change (A3−A0, point estimates).**

- Subset component (97 → 49 tasks, original labels held fixed):
  +10.2 − +9.8 = **+0.4 pts**. Restricting to the corrected subset does
  not shrink the win at all; it is, if anything, marginally larger there.
- Label component (original → corrected, same 49 tasks):
  0.0 − +10.2 = **−10.2 pts**. The entire collapse occurs when the
  labels change on an identical task set.
- Total: +0.4 + (−10.2) = −9.8 pts = 0.0 − (+9.8). ✓

**Reading.** The flip is a label effect, not a subset-composition
artifact: on the identical 49 tasks, A3's advantage is +10.2 points
under original labels and exactly 0.0 under corrected labels. This
*strengthens* the paper's Contribution-2 demonstration — the missing
cell was the one piece of evidence the "scored two ways" sentence
needed. Two precision caveats stand: the 49-task original-label CI is
wide (+1.5…+19.9), and the corrected-label CI (±8.2 pts) still cannot
exclude a real corrected-label effect of up to ~8 points, so
"non-confirmation under corrected labels" remains the correct strength
for the corrected side; what the new cell removes is the *composition*
alternative explanation for the difference between the two headlines.

Sibling cells are consistent with the full-set results: the memory
nulls on the 49 under original labels (A1−A0 −1.0, A2−A0 −2.6) match
their 97-task counterparts (−1.8, −4.6) in sign and rough magnitude.
