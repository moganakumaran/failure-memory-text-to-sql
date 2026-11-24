# Amendment A15 — Store-Transplant Verifier Ablation (Arm A1-T): Results

**Date:** 2026-11-23. **Workstream:** Paper #1 PVLDB minimum viable revision, panel-review meta-review fix item 8 (deciding issue D5 / §5.6 repair). **Protocol:** Amendment A15 in `files/Paper 1 Pilot Protocol - Failure Memory for Data Agents.md`. **Machine-readable results:** `hidden_files/mvr_a15.json` (produced by `hidden_files/analysis_a15.py`, estimators mirrored from `analysis_a14.py`: paired per-task run-mean pass@1 differences, task-level bootstrap 95% CIs, 10,000 resamples, seed 20261122).

## Design (as run)

- Arm **A1-T**: repeated-failure split, **Session 2 only**, 4 runs × 100 Session-2 pairs (primary metric on the 97 primary tasks; 3 recall-control pairs excluded as in all prior arms) = **400 trajectories**.
- Model: `gpt-5-mini-2025-08-07` (pinned snapshot), OpenAI backend.
- Harness identical to the A14 `--no-verifier` A1 ablation (verifier disabled; executed SQL accepted immediately) EXCEPT each run's retrieval store was **transplanted from that same run index's verifier-on A1 Session-1 episode journal** (`episodes_stage1_A1_run{n}.jsonl`, S1 phase), loaded as-is via the new `--transplant` mode in `pilot.py`. Only §6-legitimate episodes were loaded — no episode was fabricated or repaired, and no gold SQL entered the store or any prompt.
- Session-2 acquisition mirrored A14 exactly: acquisitions went to a shadow store, were counted, and were never retrieved (the retrieval pool stayed frozen at the transplanted store all through Session 2).
- Comparators are the **existing A14 no-verifier runs** (`traces_abl_A0_run*.jsonl`, `traces_abl_A1_run*.jsonl`), reused from stored traces — not re-run.

## Budget gate and cost (compute-fair skill: smoke-measured projection)

- Ledger before A15: **$17.8367** of the $24.00 cap ($6.16 headroom).
- Smoke (5 pairs, run 1, `--out smoke_a15`): $0.0054 total, **$0.00109/trajectory**, mean 1,946 tokens/trajectory, retrieval in 5/5 trajectories, transplant store = 24 episodes verified. Projection for 400 trajectories ≈ $0.43 → projected ledger ≈ $18.28. **Gate passed.**
- Reference points for the projection: A14 no-verifier A1 actual = $0.00112/trajectory (thin store); Stage-1 verifier-on A1 S2 = $0.00383/trajectory (upper bound).
- **Actual full-run cost: $0.5488** for 400 trajectories ($0.00137/trajectory; per-run ledger deltas: run 1 $0.1343, run 2 $0.1362, run 3 $0.1363, run 4 $0.1420). Total A15 spend including smoke: $0.5542.
- **Final ledger: $18.3909 of $24.00** (13,492 calls) — $5.61 headroom remains. No API errors occurred in any run (logs `mvr_A1T_run{1..4}.log` clean; all 400 (run, qid) pairs unique, all traces `no_verifier=True`, phase S2 only).

## Store sizes (the point of the transplant)

| Run | Store at S2 start (transplanted) | Shadow acquired in S2 | Store at S2 end |
|---|---|---|---|
| run1 | 24 | 1 | 25 |
| run2 | 23 | 0 | 23 |
| run3 | 25 | 2 | 27 |
| run4 | 28 | 1 | 29 |

Contrast with the A14 ablation's own A1 store: 2–3 episodes per run. The transplant restored the full-size store (~25 episodes/run, 100 episodes total across runs) while the agent ran verifier-off — the condition the panel said was missing from the paper.

## Retrieval

- Retrieval occurred in **364 of 400** Session-2 trajectories; **783 episodes** retrieved in total.
- Per run: run1 91/100 trajectories (192 episodes), run2 73/100 (183), run3 100/100 (196), run4 100/100 (212). (Runs 1–2 fall short of 100 because retrieval is restricted to the task's database and those runs' transplanted stores contain no episode for some databases — the same mechanism as in the main study, where A1 retrieved in 364/400 S2 trajectories.)

## Results

Levels (pass@1, primary tasks):

| Arm | Original labels (97 tasks) | Corrected labels (49 tasks) |
|---|---|---|
| **A1-T (transplant, verifier off)** | **0.6005** | **0.6173** |
| A0 no-verifier (A14) | 0.6237 | — |
| A1 no-verifier, thin store (A14) | 0.6186 | — |

**Primary contrast — A1-T − A0-no-verifier:**
- Original labels: **−2.3 points (95% CI −6.4…+1.6)**, n = 97 tasks.
- Corrected labels (secondary): +2.0 points (−4.6…+8.7), n = 49 tasks.

**Secondary contrast — A1-T − A1-no-verifier (thin store):**
- Original labels: **−1.8 points (95% CI −5.9…+2.1)**, n = 97 tasks.
- Corrected labels: 0.0 points (−6.6…+6.1), n = 49 tasks.

**Tokens (mean per S2 trajectory):** A1-T 1,892.6 vs A0-no-verifier 1,348.7 vs A1-no-verifier 1,369.0. The transplanted memory cost ~+40% tokens over the no-memory verifier-off baseline (the injected episode context) and returned no accuracy gain.

**S2 shadow acquisition (A1-T):** 4 episodes acquired across 400 trajectories, 0 unresolved failures — consistent with the A14 no-verifier pattern (acquisition can only trigger on execution-error recoveries when the verifier is off).

## Interpretation for §5.6 / D5

The panel's objection was that the A14 ablation's "memory null persists without the verifier" conclusion was established only for a nearly memory-less agent (2–3 episodes/run, retrieval in 18/100 trajectories in one run's accounting). That objection no longer applies: with a full-size transplanted store (23–28 episodes/run), retrieval in 364/400 trajectories, and the verifier off, memory still does not beat the no-memory verifier-off baseline (−2.3 points, CI −6.4…+1.6 on original labels), and the full-size store does not beat the thin store either (−1.8 points, CI −5.9…+2.1). Store size was therefore not the binding constraint on the verifier-off memory contrast, and §5.6's second conclusion ("the memory null persists without the verifier") is now supported by a well-stocked condition rather than only by the thin-store ablation. Caveats that remain: the corrected-label intervals are wide (n = 49, ±7 points); the transplanted store still contains only self-acquired, verifier-approved episodes from the verifier-on runs (the survivorship/selection structure of §6 acquisition is unchanged by design — the transplant isolates the store-size confound, not the acquisition-policy question); and A1-T's token cost is higher than both comparators, so the contrast is attempt-matched, not token-matched, as elsewhere in the study.

## Files

- Traces: `hidden_files/traces_mvr_A1T_run{1..4}.jsonl` (100 S2 trajectories each).
- S2 shadow journals: `hidden_files/episodes_mvr_A1T_run{1..4}.jsonl` (1/0/2/1 episodes).
- Logs: `hidden_files/mvr_A1T_run{1..4}.log`; smoke traces/journal: `traces_smoke_a15.jsonl` / `episodes_smoke_a15.jsonl` (excluded from analysis by the standard `smoke` filter).
- Analysis: `hidden_files/analysis_a15.py` → `hidden_files/mvr_a15.json`.
- Harness change: `hidden_files/pilot.py` — new `--transplant` flag and A1-T branch (Session-2-only repeated-split path); `"A1-T"` added to the retrieval arm lists in `run_task` (initial embedding retrieval and fingerprint re-retrieval). Existing modes untouched; `pilot_lib.py` unchanged (§6 EpisodeStore rules unmodified).
