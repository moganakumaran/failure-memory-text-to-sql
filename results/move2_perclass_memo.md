# Move 2 — Per-failure-class memory effect (Paper #1) — 2026-11-24

Post-hoc re-analysis of stored traces only. No model calls, no spend.
Script: `analysis_move2_perclass.py`. Results: `move2_perclass_results.json`.

## Question and grouping rule

Paper #1's headline on the repeated-failure split is A1−A0 = −1.8 pts
(97 primary tasks, original labels). Does that average hide a per-class
win or harm? Each S2 task is grouped by the failure class of the failure
its **paired Session-1 task** produced — the class of the recurring
failure the memory was meant to address, fixed before S2 ran. Grouping
is never by the S2 failure's own class (that would condition on the
outcome).

Label sources, in priority order:

1. The Paper #2 coding pass's reconciled human label for that
   (task, split = repeated, phase = S1) failure
   (`paper2_coding_manifest.jsonl` + `paper2_coding_reconciled.jsonl`).
   F1a/F1b fold into the F1 family (no grouped task was affected).
2. The episode journal's fingerprint class. This fallback is nearly
   vacuous: the A1 S1 journals carry no qid, and all 100 S1 episodes
   carry the single heuristic class F6 (the fingerprint class derives
   from the error signature, which is "verifier rejected" for these
   self-repaired failures). Only 1 of the 97 tasks needed it.

Tasks whose paired S1 task produced **no acquired episode in any of the
4 A1 S1 runs** (acquisition is read from the `acquired_episode` flag in
`traces_stage1_A1_*.jsonl`: 100 episodes over 47 distinct S1 qids) form
the **no-episode** stratum. They are reported, never dropped — and they
are the majority: for 51 of 97 pairs, memory had nothing pair-specific
to retrieve.

**Label coverage (of 97):** human coding-pass label 45 · journal
heuristic label 1 · no-episode stratum 51.

Estimator: the project's paired estimator (per-task run-mean pass@1,
task-level bootstrap 95% CI, 10,000 resamples, seed 20261122 reset per
contrast), as in `analysis_stage1.py` / `analysis_b02_subset.py`.

## Validation gate — PASSED

Per-class diffs weighted by task counts (including the no-episode
stratum) recombine **exactly** to both published headlines:
A1−A0 = −0.018 (CI −0.0567…+0.0206, also reproduced) and
A2−A0 = −0.0464 (−4.6 pts). Bonus check: the corrected-label per-class
cells recombine to the published 49-task A1−A0 = −0.0102.

## Primary: A1−A0 by class, original labels (GPT-5 mini)

| Class | n | A0 | A1 | A1−A0 (pts) | 95% CI (pts) |
|---|---|---|---|---|---|
| F4 aggregation/grouping | 8 | 0.563 | 0.625 | +6.3 | 0.0 … +18.8 |
| F5 value-format/domain | 8 | 0.438 | 0.375 | −6.3 | −15.6 … 0.0 |
| F7-label (gold artifact) | 8 | 0.406 | 0.344 | −6.3 | −15.6 … 0.0 |
| NONE/OTHER (unclassed) | 12 | 0.583 | 0.479 | −10.4 | −25.0 … 0.0 |
| No episode (stratum) | 51 | 0.549 | 0.554 | +0.5 | −4.9 … +6.9 |
| F1 schema link | 1 | 0.000 | 0.000 | 0.0 | descriptive only |
| F3 join/fan-out | 5 | 0.800 | 0.800 | 0.0 | descriptive only |
| F6 exec-error class | 2 | 0.500 | 0.500 | 0.0 | descriptive only |
| F9 no-change loop | 2 | 0.500 | 0.375 | −12.5 | descriptive only |

Classes with n < 8 are descriptive only (point estimates, no inference).

**No class has a CI that excludes 0.** Several intervals end exactly at
0 (a consequence of the coarse run-mean grid at small n); none crosses
to the other side. The largest point estimate, NONE/OTHER at −10.4 pts,
has a CI reaching 0.

## Secondary contrasts

- **Corrected labels (49-task subset), A1−A0:** F4 (n=6, descriptive)
  +16.7 [0.0 … +33.3]; no-episode (n=27) −0.9 [−7.4 … +5.6]; all other
  classes n ≤ 4, descriptive. Nothing excludes 0.
- **A2−A0, original labels:** F4 +3.1 [0.0 … +9.4]; F5 −15.6
  [−37.5 … +3.1]; F7-label −15.6 [−40.6 … 0.0]; NONE/OTHER −2.1;
  no-episode −1.5. Nothing excludes 0. Generic episodic memory mirrors
  the fingerprint arm's per-class pattern, including the negative
  point estimates on F5 and F7-label.
- **Qwen replication, A1−A0, original labels (same grouping):** F4
  +6.3 [0.0 … +18.8] — the same point estimate as the mini, again with
  the CI touching 0; F3 (n=5, descriptive) −20.0; F5 0.0; F7-label 0.0;
  NONE/OTHER 0.0; no-episode +0.5 [−5.4 … +5.9]. Corrected: F4 (n=6,
  descriptive) +8.3. (The grouping and the no-episode stratum are
  defined on main-study acquisition; replication acquisition was much
  thinner overall, rate 0.132.)

## Estimable vs too small

Estimable (n ≥ 8, original labels): F4, F5, F7-label, NONE/OTHER, and
the no-episode stratum. Too small for inference: F1 (1), F3 (5), F6 (2),
F9 (2) — and every corrected-label class cell except the no-episode
stratum (largest is F4 at n=6). This is a structural property of the
design, not a labelling gap: acquisition succeeded for only 47 of the
100 S1 tasks, so the has-episode classes are necessarily small.

Ambiguity/notes (43 logged in the JSON): 41 tasks had partial
acquisition (episode acquired in 1–3 of 4 runs; grouped as has-episode),
1 task used the journal fallback, 1 coded task carried a secondary
class (grouped by primary).

## Bottom line

The overall null does not hide any statistically established
per-class effect: across both models and both label views, no failure
class shows a memory effect whose confidence interval excludes zero.
The only consistent directional hint is F4 (aggregation/grouping),
positive in both models (+6.3 pts each, original labels) and on the
small corrected subsets, but its intervals touch zero throughout, so
it is a hint, not a finding. If anything, the split cuts the other
way for the unclassed NONE/OTHER failures and for F5/F7-label under
generic memory, where the point estimates are negative — and for the
majority of pairs (51/97) memory never had a pair-specific episode to
retrieve in the first place.

No manuscript text was changed. Whether any of this enters the paper
is the author's decision.
