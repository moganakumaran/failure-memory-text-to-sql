# MVR Workstream A5 — Changed-Gold Accounting for Paper #1's Corrected-Label Contrasts

**Scope:** PVLDB panel meta-review fix item 5 (PVLDB_REVIEW.md §"Ranked pre-submission fix list", item B5): *"Changed-gold counts for every corrected-label contrast (49 primary, 60 drift); changed-gold-only sensitivity analyses for the A3 flip and the drift effect."* Existing data only; no model calls; no paper text edited.
**Script:** `hidden_files/mvr_analysis5_changed_gold.py` · **Machine-readable results:** `hidden_files/mvr_analysis5.json`
**Estimator:** identical to the original analyses — paired per-task differences in run-mean pass@1 on `pass_corrected`, task-level bootstrap 95% CI, 10,000 resamples (analysis_stage1/2, analysis_a14, analysis_rep; τ-bench pass^k estimator from analysis_fixes for the pass^k rows). One deliberate deviation: each contrast reseeds `random.seed(20261122)` before its own bootstrap (the originals share one RNG stream), so every number here is independently reproducible. Point estimates are RNG-free and exact; two full-subset CIs differ from the published ones by ≤0.004 for this reason alone (flagged in §4).

## 1. The changed-gold rule and the counts

A task is **changed-gold** iff it is L1 in `manifest_v2.csv` (Jin et al. corrected SQL present) and

> normalize(gold_sql_original) ≠ normalize(gold_sql_corrected), where normalize = lowercase + collapse all whitespace runs to one space + strip.

A raw exact-string comparison gives identical classifications everywhere below, so the rule is not sensitive to the normalization choice.

| Set | L1 (audited) n | Changed-gold | Audited-unchanged |
|---|---|---|---|
| All BIRD Dev L1 tasks | 498 | **220** (44.2%) | 278 |
| Repeated-split primary corrected subset | 49 | **20** (40.8%) | 29 |
| Drift split (all 60 tasks are L1) | 60 | **26** (43.3%) | 34 |

The overall 220/498 reproduces exactly the count stated in main.tex §3.1 ("220 with SQL differing from the original gold") — an independent cross-check of the rule. Changed-gold qids, primary: 11, 28, 77, 92, 115, 242, 356, 402, 682, 1037, 1040, 1094, 1103, 1114, 1155, 1205, 1209, 1243, 1473, 1490. Drift: 5, 12, 17, 24, 25, 94, 95, 197, 198, 347, 349, 352, 366, 371, 565, 726, 846, 847, 862, 1028, 1032, 1036, 1156, 1322, 1323, 1331 (26; full lists in the JSON).

**Execution-equivalence caveat (checked, not assumed).** For the 46 distinct changed-gold tasks above, both golds were executed read-only on the original BIRD database and compared under `pilot_lib.results_equal` semantics. In **15 of 46** (primary 5/20: q77, q92, q242, q1103, q1114; drift 10/26) the string differs but the two golds return **equal results** on the undrifted database — for those tasks the corrected score of any prediction is the same as the original score (on undrifted data), so they dilute a "changed-only" subset just as audited-unchanged tasks dilute the full corrected subset. The remaining 31 return genuinely different results; no gold execution errors. A stricter "result-changed" subset would be n=15 (primary) / n=16 (drift); it was not used for the contrasts below (the panel asked for changed-gold, and n would fall further), but the counts are in the JSON (`execution_equivalence_changed_tasks`) for any follow-up.

## 2. Per-contrast results (percentage points; diff = first arm − second, corrected labels)

### Repeated split — main study (gpt-5-mini), corrected subset n=49 (changed 20 / unchanged 29)

| Contrast (paper location) | Full corrected (n=49), as published | Changed-only (n=20) | Unchanged-only (n=29) |
|---|---|---|---|
| A1−A0 (§5.1) | −1.0 (−6.1…+4.1) | −1.3 (−8.8…+6.3) | −0.9 (−7.8…+6.0) |
| **A3−A0 (§5.2)** | **0.0 (−8.2…+8.2)** | **−7.5 (−18.8…+1.3)** | +5.2 (−5.2…+16.4) |
| A3−A1 (§5.2) | +1.0 (−7.7…+10.2) | −6.3 (−20.0…+6.3) | +6.0 (−5.2…+18.1) |
| A2−A0 (§5.3) | −4.6 (−10.7…+1.0) | −5.0 (−15.0…+3.8) | −4.3 (−12.1…+2.6) |
| A2−A1 (§5.3) | −3.6 (−7.7…+0.5) | −3.8 (−10.0…+2.5) | −3.5 (−9.5…+1.7) |
| Ablation (verifier-off) A1−A0 (§5.6) | +2.0 (−4.1…+8.2) | +1.3 (−10.0…+12.5) | +2.6 (−4.3…+9.5) |
| pass² A1−A0 (§5.7) | −3.7 (−12.2…+4.4)† | −7.5 (−19.2…+1.7) | −1.2 (−12.6…+10.9) |
| pass⁴ A1−A0 (§5.7) | −6.1 (−18.4…+6.1) | −15.0 (−30.0…0.0) | 0.0 (−17.2…+17.2) |

### Replication — Qwen2.5-Coder-32B (§5.5), corrected subset n=49 (changed 20 / unchanged 29)

| Contrast | Full corrected (n=49), as published | Changed-only (n=20) | Unchanged-only (n=29) |
|---|---|---|---|
| A1−A0 | +3.1 (0.0…+8.2) | **0.0 (0.0…0.0)**‡ | +5.2 (0.0…+13.8) |
| A3−A0 | +4.1 (−4.1…+12.2) | +5.0 (0.0…+15.0) | +3.5 (−6.9…+13.8) |
| A3−A1 (in pilot_rep_results.json; not in paper text) | +1.0 (−8.2…+10.2) | +5.0 (0.0…+15.0) | −1.7 (−15.5…+12.1) |

‡ Degenerate but real: on all 20 changed-gold tasks Qwen's A0 and A1 per-task corrected pass@1 are identical (17 tasks both 0.00, 3 both 1.00; subset level 0.150 for both arms), so every paired difference is exactly 0. Verified directly from traces_rep_*.

### Drift split (§5.4, Amendment A14), corrected subset n=60 (changed 26 / unchanged 34)

| Contrast | Full corrected (n=60), as published | Changed-only (n=26) | Unchanged-only (n=34) |
|---|---|---|---|
| **Paired drift effect, A0 drifted − undrifted** | **−15.4 (−26.7…−4.2)**† | **−14.4 (−31.7…+2.9) — n.s.** | −16.2 (−30.9…−1.5) |
| A1−A0 (live memory, drifted) | −0.8 (−5.0…+3.3) | −1.0 (−7.7…+7.7) | −0.7 (−5.2…+3.7) |
| A4−A0 (stale memory, drifted) | +1.3 (−2.9…+5.4) | +1.0 (−7.7…+9.6) | +1.5 (−1.5…+4.4) |
| A4−A1 (stale vs live, drifted) | +2.1 (−1.7…+6.7) | +1.9 (−3.8…+9.6) | +2.2 (−2.2…+8.1) |

Supplementary (not separately reported in the paper; computed because they decompose the drift effect — see §3):
- Drift effect, **silent** tasks only (n=33; changed 14): **+6.1 (−5.3…+18.2)** full; +10.7 changed-only; +2.6 unchanged-only.
- Drift effect, **overt** tasks only (n=27; changed 12): **−41.7 (−57.4…−26.9)** full; −43.8 changed-only; −40.0 unchanged-only.
- Silent A4−A0 corrected (n=33): +2.3 (−5.3…+9.9); silent A1−A0 corrected: −1.5 (−9.1…+6.1); overt A4−A0 corrected: exactly 0.0 with both arms at level 0.000 (see §3).

## 3. Headline readings

1. **The A3 label-flip strengthens on changed-gold tasks.** On the full 49 the corrected A3−A0 is 0.0; restricted to the 20 tasks whose gold actually changed it is **−7.5 points** (n.s., CI −18.8…+1.3), while on the 29 audited-unchanged tasks it is +5.2. The composition is consistent with the paper's label-artifact reading — A3's original-label win lives disproportionately where the gold was wrong — but at n=20 the interval is ±11 points, so this is directional support, not confirmation. (Note 5 of those 20 are result-equal gold rewrites, §1, so the effective label-changed n is smaller still.)
2. **No memory contrast changes sign or significance on changed-only subsets.** Mini A1−A0, A2 contrasts, the ablation contrast, and all drift memory contrasts (A1−A0, A4−A0, A4−A1) are materially the same on changed-only as on the full corrected subset — all null. The corrected-label memory null is not a dilution artifact of audited-unchanged tasks.
3. **The corrected paired drift effect (−15.4) does NOT survive restriction to changed-gold tasks as a significant effect** (−14.4, CI −31.7…+2.9 at n=26), and the supplementary split shows why, and it is not a gold-change story: the effect is **entirely overt-task-driven** (−41.7 on 27 overt tasks; **+6.1, wrong sign, on the 33 silent tasks**). Mechanism, verified from the traces: under the corrected view the unadjusted corrected gold is executed on the drifted database; on overt tasks (dominated by column renames) **every arm scores exactly 0.000 on every overt task** (A0 and A4 levels both 0.000, n=27), while the undrifted control scores 0.417 — so the "effect" on overt tasks is a constant scoring failure of the unadjusted gold, not agent behavior. This is the panel's W7/D4(iii) invalid-scoring concern, quantified: the corrected drift view's only significant number is produced by the subset where its scoring is degenerate. Repair belongs to the drift re-scoring workstream (fix item 6); A5 reports the accounting.
4. **Replication corrected contrasts are unchanged in character on changed-only tasks** (A1−A0 exactly 0.0 task-by-task; A3−A0 +5.0, n.s.).

## 4. Reproduction check — anything not reproduced

Every corrected-label contrast in main.tex §5 was located and reproduced from the traces. All point estimates match the published values **exactly**. All CIs match exactly except two, which differ only by RNG-stream position (see header): pass² corrected CI lower bound −12.2 here vs −11.9 in fixes_results.json, and the A14 corrected drift-effect CI lower bound −26.7 here vs −27.1 in a14_results.json. No contrast could not be reproduced. Two paper values exist only in the paper text (no JSON ever stored them — the Stage 2 analysis script computed corrected contrasts for nothing except via pass^k levels): mini A3−A0 / A3−A1 / A2−A0 / A2−A1 corrected and the drift-table corrected column; all four/five were recomputed here from traces_stage1/stage2/drift traces and match the paper's printed values, so they are now backed by a stored script + JSON for the first time.

## 5. The "49 vs 48" question — resolved

**There is no Stage-1-vs-replication discrepancy.** The corrected subset is the *same set of tasks* in both studies:

- Tasks with `pass_corrected` present, all 100 repeated-split S2 tasks: **51 qids, identical set** in Stage 1 traces and replication traces (per-arm as well: 51 for every arm in both studies).
- Removing the 3 recall-control pairs (q850, q1326, q1479 — of which q850 and q1479 are L1, q1326 is not) leaves **49 primary tasks in both studies**: Stage 1 corrected n=49 (pilot_stage1_results.json) and replication corrected n=49 (pilot_rep_results.json), same 49 qids (listed in the JSON, `primary_corrected_subset.qids`).

**Where "48" actually comes from:** it is the *complement* within the 97 primary tasks — **97 = 49 with corrected labels (L1) + 48 without (L2)**. That is the comparison the panel itself makes (R3 Q2 and fix item 5: "composition table comparing the 49 corrected vs. 48 uncorrected primary tasks"). The 48 uncorrected primary qids are listed in the JSON (`primary_uncorrected.qids`). No corrected-label contrast anywhere in the study — Stage 1, Stage 2, drift, ablation, pass^k, or replication — runs on 48 tasks; any "Stage 1 = 49 vs replication = 48" framing is a misreading of the panel's 49-corrected-vs-48-uncorrected split. (Composition comparison of the 49 vs the 48 is the separate half of fix item 5 and is not part of this workstream's deliverable.)
