# MVR Analysis 6 — Drift-adjusted corrected golds + re-scoring of stored drift trajectories

**Workstream A6, Paper #1 PVLDB minimum viable revision — panel fix item 6 (meta-review §B; decides D4 layer iii / R1 W7).**
Existing data only. **No model calls. No paper text edited.**
Script: `mvr_analysis6_rescore.py` · Numbers: `mvr_analysis6.json` · Adjusted golds: `mvr_drift_adjusted_corrected_golds.jsonl` (60 tasks).

## 1. What was wrong

In `pilot.py`, drift-phase scoring executes Jin et al.'s corrected SQL on the **drifted** database (`corr_sql` executed on `db_path`, which is the drifted DB in the drift phase), while the original-label view correctly uses the drift-adjusted gold (`drifted_gold_sql`). Consequences, verified by execution:

- **All 23 schema_column_rename tasks:** the unadjusted corrected gold does not execute on the drifted DB (`no such column`) for 22 of 23 tasks, so `pass_corrected` was **False for every arm and run by construction** (stored drift traces: 0/276 corrected passes on rename tasks). The one exception, q25, executes only because its corrected SQL never references the renamed column (see §4).
- **Value-recode (10 tasks) and category-merge tasks whose corrected SQL contains the drifted literal (2 of 9):** the unadjusted gold filters on pre-drift literals that no longer exist (recode) or no longer contain the merged rows (merge), returning the wrong expected set.
- The remaining 25 tasks (unit change 9, type change 4, temporal grain 4, null semantics 1, and 7 merges whose corrected SQL lacks the merged-away literal) were **not** mis-scored: for these, `build_drift.py` itself leaves the gold SQL unchanged and obtains the expected result by executing on the drifted DB — exactly what the old corrected view did.

## 2. Method

For each of the 60 drift tasks, the corrected SQL from `manifest_v2.csv` (`gold_sql_corrected`, Jin et al.) was transformed with the **same operator transform `build_drift.py` applied to the original gold**, with parameters taken from `drift_spec.csv`'s `detail` field (the exact table/column/value the original build used):

| Operator | Transform applied to corrected SQL (mirrors `build_drift.py`) |
|---|---|
| schema_column_rename (23) | Replace old column name with `<name>_v2` (word-boundary, outside string literals) |
| data_value_recode (10) | `'<v>'` → `'<v>_X'` (global `str.replace`, as in the original) |
| category_merge (9) | `'<gone>'` → `'<keep>'` (global `str.replace`) |
| data_unit_change (9), schema_type_change (4), temporal_grain_change (4), null_semantics_change (1) | SQL unchanged — `build_drift.py` sets `drifted_gold = gold` for these; the expected result comes from executing on the drifted DB |

**Rename validation** (the same check `build_drift.py` used for original golds): the adjusted gold executed on the drifted DB must reproduce the corrected gold's result on the **original** DB exactly (multiset, order-sensitive if ORDER BY). 22/23 passed with the global replacement; q25 required the fallback in §4.

**Re-scoring:** stored drift trajectories (arms A0/A1/A4, phase `drift`, 720 traces = 60 tasks × 4 runs × 3 arms) were re-scored against the adjusted expected results using `pilot_lib.results_equal` semantics. For the 18 identity-operator tasks the adjusted SQL is textually identical to the corrected SQL, so the new pass is definitionally the stored pass; stored flags were carried over and verified by re-execution (216/216 traces agree). The undrifted side of the paired drift contrast (A0 on original DBs, `traces_fix_ctrl_*`) was already scored validly — Jin SQL on the original DB — so A14's per-task data is reused unchanged (undrifted corrected level 0.4458 under both views).

**Estimators:** identical to `analysis_a14.py` — per-task run-mean pass@1, paired task-level bootstrap, 10,000 resamples, seed 20261122. Point estimates of every OLD contrast below reproduce A14 / §5.4 **exactly**; a few CI bounds differ from the published ones by ≤0.4 pt because the bootstrap RNG stream position differs (contrast evaluation order). Execution limits: 20 s gold / 15 s predicted (pilot used 10 s), 90 s retry for interrupted golds, enlarged SQLite page cache (speed only; does not change result sets).

## 3. Results — old vs new corrected view (§5.4 contrast set)

Percentage points, paired pass@1 differences with bootstrap 95% CIs. Old = as published in §5.4 / A14 (stored `pass_corrected` flags). New = drift-adjusted corrected golds. n = 60 tasks throughout (33 silent for the silent rows).

### Levels (pass@1, corrected labels)

| Level | Old | New |
|---|---|---|
| A0 undrifted (paired control) | 0.446 | 0.446 (unchanged by construction) |
| A0 drifted | 0.292 | **0.363** |
| A1 drifted (live memory) | 0.283 | **0.317** |
| A4 drifted (stale memory) | 0.304 | **0.350** |

### Contrasts

| Contrast (corrected labels) | Old (published) | New (drift-adjusted) |
|---|---|---|
| **(a) Paired drift effect, A0** (drifted − undrifted) | **−15.4** (−27.1…−4.2), significant | **−8.3** (−17.5…+0.4), **not significant** |
| **(b) A4 − A0 on drift** (stale memory) | +1.3 (−2.9…+5.4) | −1.3 (−6.3…+3.8) |
| **(c) A1 − A0 on drift** (live memory) | −0.8 (−5.0…+3.3) | −4.6 (−10.0…+0.8) |
| A4 − A1 on drift (stale vs live) | +2.1 (−1.7…+6.7) | +3.3 (−2.1…+9.2) |
| Paired drift effect, A0, **silent only** (33) | +6.1 (−5.3…+18.9) | −9.8 (−24.2…+3.8) |
| A4 − A0, **silent only** (33) | +2.3 (−4.6…+9.9) | +1.5 (−3.8…+6.1) |
| A1 − A0, **silent only** (33) | −1.5 (−9.1…+6.1) | −5.3 (−10.6…−0.8) |

Sanity (original labels, stored flags, unchanged by this analysis): paired drift effect −8.3 (−18.3…+1.7 published); A1−A0 −4.6; A4−A0 −1.7; A4−A1 +2.9; A4−A0 silent exactly 0.0 — all point estimates reproduced exactly.

### Interpretation — does the −15.4 survive?

**No.** Under drift-adjusted corrected golds the paired corrected drift effect is **−8.3 points (−17.5…+0.4)** — numerically identical to the original-label paired effect (−8.3) and **no longer significant**. The old −15.4 was an artefact of the scoring rule, with two stacked components: (i) on the 23 rename tasks every corrected pass was mechanically False on the drifted side while the undrifted side scored normally, manufacturing ≈7 points of spurious "drift effect"; (ii) on recode/merge tasks the unadjusted gold's expected sets were wrong in the direction of penalising adaptation. The old view's silent-subset number makes the artefact visible in the other direction: it implied drift *improved* corrected accuracy by +6.1 points on silent tasks; the adjusted view gives −9.8 (−24.2…+3.8).

What survives:

- **Stale memory (A4) remains neutral under drift on corrected labels**: −1.3 (−6.3…+3.8) overall, +1.5 (−3.8…+6.1) on silent tasks — consistent with the original-label view (−1.7 overall; exactly 0.0 silent). The §5.4 stale-memory conclusion is robust to the scoring repair; if anything the corrected view now agrees with the original-label view instead of sitting +3 points above it.
- **Live memory (A1) remains null under drift**: −4.6 (−10.0…+0.8), now identical to the original-label point estimate.
- The one nominally significant new number, A1−A0 on silent tasks (−5.3, −10.6…−0.8), is a 33-task subset contrast among many; it should be read with the same multiplicity/precision caution the panel applied elsewhere, not as a new headline.
- §6's phrasing "drift costs … 15 [points] on corrected labels" is **not supported** after the repair; the defensible statement is ≈8 points on both label views, significant on neither at n = 60.

## 4. Per-operator transform outcomes and failure log

All 60 adjusted golds execute on their drifted DBs. **No task was dropped; no transform ultimately failed.** New-view contrasts are on the full n = 60.

| Operator | n | Applied (SQL changed) | Identity / no-op | Adjusted gold executes | Expected result changed vs old view |
|---|---|---|---|---|---|
| schema_column_rename | 23 | 23 (22 global + 1 fallback) | 0 | 23/23 | 22 tasks |
| data_value_recode | 10 | 10 | 0 | 10/10 | 9 tasks |
| category_merge | 9 | 2 (q98, q1471) | 7 no-op (literal absent) | 9/9 | 2 tasks |
| data_unit_change | 9 | 0 | 9 identity | 9/9 | 0 |
| schema_type_change | 4 | 0 | 4 identity | 4/4 | 0 |
| temporal_grain_change | 4 | 0 | 4 identity | 4/4 | 0 |
| null_semantics_change | 1 | 0 | 1 identity | 1/1 | 0 |
| **Total** | **60** | **35** | **25** | **60/60** | **33 tasks** |

Explicit log of every non-routine case (nothing silent):

- **q25 (rename, frpm.CDSCode → CDSCode_v2) — global replace WRONG, fallback used.** The corrected SQL joins `satscores` to `schools` (alias `sc`) and references `sc.CDSCode` — the *schools* column, which was not renamed; it never references `frpm.CDSCode`. The global replacement produced `sc.CDSCode_v2` (`no such column`). The alias-restricted fallback (replace only occurrences qualified by the renamed table/`frpm` aliases — here, none) validates: adjusted result on the drifted DB equals the corrected result on the original DB. q25 is also the only rename task whose *old* gold executed on the drifted DB, and its expected result is unchanged by the repair.
- **q346, q352, q371 (rename, cards.id → id_v2) — slow golds, succeeded on the 90 s retry.** First-pass executions hit the 20 s interrupt under disk contention; all three execute and pass rename validation on retry. Transform itself routine (1–2 occurrences each).
- **q1483 (recode, '201308' → '201308_X') — transform applied, expected result unchanged.** The adjusted gold's result set on the drifted DB is identical to the unadjusted gold's (the recoded value does not affect this query's returned aggregate). Recorded in the golds file; not an error.
- **Category-merge no-ops (7): q197, q198, q200, q539, q549, q861, q1334.** The merged-away literal does not appear in the corrected SQL (nor in the original gold — `build_drift.py`'s drifted gold is likewise unchanged for these tasks). Adjusted SQL = corrected SQL; the expected result is still the drift-adjusted one because it is executed on the drifted DB. Old and new scoring coincide for these tasks.
- **q116 (type change, identity) — pathologically slow gold.** Jin's corrected SQL for q116 reads tens of GB uncached and was interrupted at the pilot's 10 s limit (and at 20 s uncached) on both original and drifted DBs; it completes with the enlarged page cache used here. Its new passes are the stored flags by the identity rule regardless, and the re-execution agreement check (below) reproduced all 12 of its traces.

## 5. Validation of the re-scoring pipeline

- **Old-view reproduction:** re-scoring the 504 transformed-operator traces against the *unadjusted* gold reproduces the stored `pass_corrected` flags for **497/504 (98.6%)**. The 7 disagreements (q366 A0 runs 1–4 + A4 run 3; q347 A4 runs 3–4; all stored False → re-scored True) are all recode tasks where the old gold's expected set is empty and re-execution finds the predicted result also empty; a pilot-faithful 10 s re-execution also returns True, so the stored False is consistent with a 10 s execution timeout in one of the two executions during the original run. All OLD numbers in §3 use the stored flags, so published values are reproduced regardless.
- **Identity-task re-execution:** 216/216 traces agree with stored flags.
- **Rename validation:** 23/23 adjusted golds reproduce the corrected-on-original result set exactly.
- **Old point estimates:** every OLD contrast and level in §3 matches A14 / §5.4 exactly (CI bounds within 0.4 pt; bootstrap stream position only).

## 6. Files

- `mvr_drift_adjusted_corrected_golds.jsonl` — per task: qid, database, operator, drift type, detail, original corrected SQL, adjusted SQL, transform status/note, rename validation, execution status of adjusted gold on drifted DB / old gold on drifted DB / corrected gold on original DB, expected-result-changed flag + reason.
- `mvr_analysis6.json` — all levels, contrasts (old/new, overall + silent), per-operator counts, validation agreement, failure log (empty at completion; the §4 cases are recorded per-task in the golds file and in `per_operator`).
- `mvr_analysis6_rescore.py` — the script (transforms, validation, re-scoring, estimators).
