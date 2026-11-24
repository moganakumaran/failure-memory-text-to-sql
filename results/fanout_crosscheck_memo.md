# BIRD-FanOut cross-check of the 49-task corrected subset — 2026-11-24

Follow-up to the morning brief of 2026-11-24 (Paper #1 angle, move 1):
cross-check the 49-task corrected subset against the public BIRD-FanOut
list, to separate "annotation error" from "fan-out error" as distinct
label-defect classes. No model calls; pure join of stored data plus
execution of stored SQL on the local BIRD dev databases.

## Sources

- 49 qids: `b02_subset_results.json` (`corrected_subset_qids`), derived
  from `manifest_v2.csv` (BIRD dev_20240627, 1,534 tasks) + `splits_repeated.csv`.
- BIRD-FanOut June 2024 pilot: `bird_fanout_june2024_subset.jsonl`
  (93 records, SHA256 6b5ed59c…dfa4a5e9), from
  https://github.com/ahmed-mahran/misqal (`benchmarks/bird-fanout/`,
  same dev release as Paper #1's substrate). Paper: Mahran,
  arXiv:2611.29009 (21 Nov 2026).
- BIRD-FanOut dev 2025-11-06: `bird_fanout_dev20251106_subset.jsonl`
  (127 records, SHA256 136e0c27…a056e), same repo,
  `benchmarks/bird-fanout-20251106/` (cleaned release; 102 harness
  questions after gold review).
- Scripts: `fanout_crosscheck.py` (join), `fanout_split.py` (per-group
  contrasts, reusing the B-02 estimator). Results:
  `fanout_crosscheck_results.json`, `fanout_split_results.json`.

## Alignment check (qid join validity)

- June 2024 pilot: database AND question text match the manifest for
  93/93 records. Clean join.
- Dev 2025-11-06: database matches 127/127; question text matches
  116/127. The 11 mismatches are all rewordings by the cleaned release
  on the same topic in the same db (6 carry `old_question`; the other 5
  inspected manually, e.g. q1173 differs by one comma). None of the 11
  is in the overlap with the 49, so the overlap counts are unaffected.

## Overlap: the 49 are overwhelmingly not fan-out

| List | Records | Overlap with 49 | Of the 49 |
|---|---|---|---|
| June 2024 pilot (same substrate) | 93 (64 inflated, 21 intended, 5 contested, 3 benign) | 4 | 8.2% |
| Dev 2025-11-06 (cleaned release) | 127 (33 inflated, 36 fixed_in_release, 42 intended, 12 contested, 4 benign) | 5 | 10.2% |
| Union (either list) | — | 6 | 12.2% |

Overlap detail (June 2024 pilot): inflated 1037 (european_football_2),
1243 (thrombosis_prediction), 1490 (debit_card_specializing); intended
(control, gold correct) 208 (toxicology). Dev 2025-11-06 adds:
fixed_in_release 273 (toxicology), 1037, 1243; inflated 1490 (still
inflated in the cleaned release); intended 1040 (european_football_2).
Union of fan-out-defective (inflated or fixed_in_release) inside the 49:
**4 tasks — 273, 1037, 1243, 1490**. Context: 5 of the 97 primary tasks
are in the June 2024 pilot list; 7 in the 2025 list.

Note: 29 of the 49 have Jin corrected SQL byte-identical to the original
gold (audited-unchanged); they score identically under both keys and
contribute 0 to the label component by construction. The flip lives in
the other 20.

## Split: the flip is not a fan-out artefact

A3−A0 on the 49, split by fan-out membership (B-02 estimator; validation
cells V1/V2 reproduced exactly before computing anything new):

| Group | n | A3−A0 original labels | A3−A0 corrected labels |
|---|---|---|---|
| Fan-out-defective (broad: 273, 1037, 1243, 1490) | 4 | +6.25 pts, contrib. +0.51 pts of the +10.2 | −6.25 pts, contrib. −0.51 pts of 0.0 |
| Rest of the 49 | 45 | **+10.56 pts (CI +1.11…+21.11)**, contrib. +9.69 pts | +0.56 pts (CI −8.33…+9.44), contrib. +0.51 pts |
| All 49 | 49 | +10.2 pts (CI +1.53…+19.9) | 0.0 pts (CI −8.16…+8.16) |

Per-task diffs (original → corrected) for the 4 fan-out tasks: 273 −0.25 →
−0.25 (unchanged); 1037 +0.50 → 0.0 (the only fan-out task whose
scoring moves); 1243 0.0 → 0.0; 1490 0.0 → 0.0. The n=4 CIs are
descriptive only; no inference is drawn from them. The point stands on
arithmetic, not on the CIs: 45 non-fan-out tasks carry +9.69 of the
+10.2 original-label effect and flip to +0.56 under corrected labels.

**Conclusion: annotation error and fan-out error are distinct defect
classes in this subset, and the label flip (+10.2 → 0.0) is an
annotation-error phenomenon, not a fan-out artefact.**

## Correction agreement (executed on the local dev DBs)

- q1037: Jin's corrected SQL == Mahran's corrected SQL (normalised) ==
  2025-release gold; all return 28.87 vs original gold 24.57. Three
  independent corrections agree exactly.
- q1243: both fix the fan-out (original gold 1.20 → Jin 75.0,
  Mahran/release 72.73). Residual gap is the ">55" age definition
  (Jin: exact date arithmetic; Mahran/release: year difference), not
  fan-out.
- q1490: both fix the fan-out the same way (COUNT DISTINCT customers).
  Residual gap is the denominator population (Jin LEFT JOIN counts all
  LAM customers, 98.25; Mahran INNER JOIN counts only LAM customers
  with rows, 99.53; original gold 98.53 — the defect is nearly
  result-neutral here).
- q273: Jin's corrected SQL is byte-identical to the original gold
  (audited-unchanged); the fan-out fix exists only in the 2025 release
  (3.14 → 28.95, COUNT DISTINCT molecules). Jin's audit missed this
  one; Mahran's audit and the release caught it. The two audits are
  complementary, not redundant.

## What this does and does not do for the paper

- DOES: lets §3/§5 say, with numbers, that the 49-task label defect
  is annotation error distinct from fan-out (only 4/49 fan-out-defective
  on either list; the flip survives — +10.6 → +0.6 — on the 45
  non-fan-out tasks alone). Strengthens the benchmark-validity section
  alongside Mahran and Reward Blindness. Cite Mahran arXiv:2611.29009
  (BIRD-FanOut, CC BY-SA 4.0 data) if used.
- DOES NOT: report the memory effect per failure class (F1–F9) — the
  brief's move 2, still undone. That needs per-task failure-class labels
  joined to the stored traces; it is the natural next step, not part of
  this memo.
- No manuscript text was changed. Whether to add a sentence (or a
  footnote) is Mohan's call; the numbers above are the verified basis.

## Limitations (stated plainly)

- BIRD-FanOut labels are LLM-judge labels: the repo README states
  "Every label and correction comes from LLM judges, with checks by
  Claude agents; no person labelled the data." Treat the 4-task overlap
  as judge-labelled, not human-adjudicated.
- The n=4 fan-out group cannot support inference; the split conclusion
  rests on the arithmetic decomposition (+9.69 of +10.2 sits in the
  n=45 group, whose CI excludes 0 under original labels), not on the
  small group's CI.
- The 2025-11-06 list describes a different (cleaned) release; it is
  used here only as corroboration, with rewordings recorded above. The
  June 2024 pilot is the substrate-matched list and the primary basis.

## Incorporated into the paper — 2026-11-24

On the author's approval, the cross-check result was added to §5.2 of
both versions (arXiv named manuscript and PVLDB main.tex) as a closing
passage, with Mahran (arXiv:2611.29009) cited and added to both
bibliographies (25 entries). The fan-out scripts and results were
mirrored into the public repo (code/fanout_crosscheck.py,
code/fanout_split.py, results/fanout_crosscheck_results.json,
results/fanout_split_results.json, results/fanout_crosscheck_memo.md)
and committed locally. PVLDB main.pdf rebuilt: 12 pages, unchanged.
