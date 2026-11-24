# Phase C Revision Notes — Paper #1 PVLDB Minimum Viable Revision (text phase)

**Date:** 2026-11-23. **Scope:** text revisions T1–T9 to `main.tex`, driven by PVLDB_REVIEW.md (meta-review text fixes 1–4; issues D1–D5) and the MVR result deliverables (A5 changed-gold accounting, A6 drift re-scoring, A15 store-transplant ablation). No numbers were invented; every new number traces to an MVR deliverable below. Unaffected numbers are unchanged (verified §"Verification").

## Page accounting (final build)

- Total: **11 pages**. Bibliography starts on **p. 10**; Appendix A (prompts) is p. 11.
- Body + appendix ≈ **10 pages ≤ 12** (limit excludes the bibliography). PASS with ~2 pages of headroom.
- Build: pdflatex → bibtex → pdflatex ×2, 0 errors, 0 undefined citations/references. (One cosmetic `OMS/cmtt` font-shape warning, pre-existing.)

## T1 — Title + framing rescope (D1/D2) — DONE

- **New title as typeset:** "Episodic Failure Memory Does Not Help Text-to-SQL Agents: A Compute-Fair, Corrected-Label Evaluation on BIRD [Experiment, Analysis & Benchmark]".
- Abstract rewritten: the tested system is now described as "embedding-retrieved raw episodic traces of the agent's own verified self-repairs, in two variants of one retrieval design," with the fingerprint fast-path's 9/400 firing stated in the abstract itself. "in either of two implementations" deleted.
- Same redescription propagated to: §1 ("both variants of the episodic-retrieval design we test"), Contribution 1 ("One episodic-retrieval design in two variants…"), §3.3 A2 item ("variants"), §5.3 (already honest; kept, plus the metadata clause under T8), §6 conclusion 1, §8. Every "two implementations" phrasing is gone (grep: 0 occurrences).

## T2 — §2 "strongest form" withdrawn (D2) — DONE

- The sentence claiming the null is "a statement about the strongest form of the memory hypothesis in this literature, not about a strawman" is deleted (grep: "strongest form" = 0).
- Replacement states what is tested (verbatim replay of raw traces of verified self-repairs; no consolidation, no distillation) and what is not (Reflexion's verbal reflections, ExpeL's distilled cross-task insights, consolidated stores), and positions the null as applying to the episodic-replay form.

## T3 — Corrected drift numbers (A6) — DONE

Source: `hidden_files/mvr_analysis6_drift_rescoring.md` / `mvr_analysis6.json`.

- §5.4: corrected paired drift effect is now **−8.3 pts (−17.5…+0.4, n.s.)**, identical to the original-label effect; corrected A0 drifted level **0.363** (was 0.292); Table 1 corrected column replaced: A1−A0 **−4.6 (−10.0…+0.8)**, A4−A0 **−1.3 (−6.3…+3.8)**, A4−A1 **+3.3 (−2.1…+9.2)**; silent corrected A4−A0 **+1.5 (−3.8…+6.1)** added. Stale-memory neutrality conclusion kept (holds on both views).
- A methodological note in §5.4 explains why the earlier **−15.4** was invalid (unadjusted corrected golds fail to execute on 22/23 rename tasks → drifted-side corrected passes mechanically false) and presents the adjusted view as the correct one. This is the only context in which "−15.4" still appears (2 occurrences, both explicitly as the repudiated artifact; §7's drift bullet is the second).
- §3.2 now specifies the corrected-drift scoring rule (same operator transforms applied to Jin's corrected SQL; execution-validated 60/60) and states why the adjustment is not optional.
- §6 conclusion 3 and the abstract now say "about 8 points on both label views," with significance stated honestly (neither interval excludes zero at n = 60). The old "15 points on corrected labels" claim is deleted everywhere (grep: 0).
- One A6 subset number added with an explicit multiplicity caution, not as a headline: silent adjusted-corrected A1−A0 **−5.3 (−10.6…−0.8)** (§5.4).
- Figure 2 needed no change: its drift group is original-label only (per its caption/description); all corrected-drift changes are text/table.

## T4 — §5.6 verifier ablation + A15 transplant (D5) — DONE

Source: `hidden_files/mvr_a15_transplant_results.md` / `mvr_a15.json`.

- §5.6 keeps the verifier-harm result unchanged (−8.5 A0 / −9.8 A1; levels 0.624/0.619).
- New transplant paragraph: A1-T (Amendment A15), verifier-off agent with stores transplanted from the verifier-on runs — **23–28 episodes/run** at S2 start (vs 2–3), retrieval in **364/400** trajectories (783 episodes). A1-T pass@1 **0.601 orig / 0.617 corrected** (A15: 0.6005/0.6173, rounded to house 3dp). Primary A1-T − A0-no-verifier **−2.3 (−6.4…+1.6)** orig, **+2.0 (−4.6…+8.7)** corrected; secondary vs thin-store A1-no-verifier **−1.8 (−5.9…+2.1)** orig, **0.0** corrected; A1-T tokens 1,893 vs 1,349 (**~+40%**).
- Conclusion rewritten: the null persists without the verifier with a thin store **and** with a well-stocked store; store size was not the binding constraint. The verifier-coupling design finding is kept; the store-provenance caveat now points to §7's new survivorship bullet.
- §4 cost sentence added: A15 cost $0.55 (A15 actual: $0.5488 full run; $0.5542 incl. smoke).

## T5 — Changed-gold reporting (A5/D4) — DONE

Source: `hidden_files/mvr_analysis5_changed_gold.md` / `mvr_analysis5.json`.

- §3.1: corrected subsets are **20 changed / 29 audited-unchanged** (primary, n = 49) and **26/60 changed** (drift). Execution-equivalence caveat added: **15 of 46** distinct changed-gold tasks are string-different but execution-equal on the undrifted DB → result-changing subsets are 15 (primary) / 16 (drift).
- §5.1: changed-only A1−A0 **−1.3 (−8.8…+6.3)** — memory null is not a dilution artifact.
- §5.2: A3 flip sensitivity — changed-only **−7.5 (−18.8…+1.3)** vs unchanged-only **+5.2 (−5.2…+16.4)**; framed as directional support, explicitly still a non-confirmation at n = 20.
- §5.5: replication changed-only corrected A1−A0 **exactly 0.0** (all per-task paired differences zero).

## T6 — Scorer specification (R3 W7) — DONE

Source: `hidden_files/pilot_lib.py` (`results_equal`, `exec_sql`) and `pilot.py` (scoring calls, lines 149–156, 231–238).

§4 now specifies, exactly as implemented: own scorer, not the official BIRD script; predicted and gold SQL both executed read-only under the same 10 s limit, result sets fetched up to 100,000 rows; prediction error/timeout/absent → incorrect; gold error/timeout → comparison false for every arm; comparison stringifies every cell value; column names never compared, column order matters only via row position; ORDER BY in the gold → ordered list equality, otherwise multiset (sorted-tuple) equality with duplicates counted; **no numeric tolerance** (1 ≠ 1.0 after string conversion); dates/timestamps compare as stored strings; NULLs pass through the same string conversion on both sides. Nothing in the code was ambiguous on these points.

## T7 — Decoding disclosure — DONE, WITH ONE FLAGGED DEVIATION FROM THE BRIEF

Source: `hidden_files/pilot_lib.py` (`call_openai`, `call_openrouter`; reached via `pilot.py`'s `make_caller`).

- Main study (§4): requests contained only model, a single user-turn message, and `max_completion_tokens` = 4000. **No temperature or any other sampling parameter was sent**; provider defaults applied and were not recorded further. This matches the brief.
- **Replication: the brief's assumption is contradicted by the code.** `call_openrouter`'s request body explicitly includes `"temperature": 0`. Since the task's primary instruction was to describe exactly what parameters were sent (and R3 explicitly asked for decoding parameters), §4 states this fact: "Replication requests, sent through OpenRouter, were constructed the same way except that they set temperature to 0 in the request body." No temperature value is claimed anywhere else, and none for the main study. **Flagged for the parent/user: if the "no temperature value anywhere" instruction was meant to override the code, this one sentence in §4 is the place to strike — but it is true, it is in the released harness, and a reviewer can read it there.**

## T8 — Small items — DONE

- (a) **L4 (§3.1):** operational criterion now stated from the substrate spec (more than one defensible correct answer, no corrected gold resolving it), with the explicit note that 0 tasks met it and the tier was never used.
- (b) **A14/A15 status (§4):** primary contrasts identified as the pre-registered ones; A14 (post-critique) and A15 (revision) labelled post-hoc additions under dated amendments. Amendment ranges updated A1–A14 → **A1–A15** in §4 and Artifact Availability.
- (c) **Preprint flags:** added where the text leans on them — StaleBench (Murshed 2026, ×2), Experience Rot (Xu et al. 2026), WikiTrace (Lee et al. 2026), Benchmarks' Last Exam (Zhu and Cat 2026), DataAgentBench (2026), DABstep, Jayaram et al. 2026 (§7). All seven are arXiv-only @misc entries in refs.bib (verified); refs.bib itself unchanged.
- (d) **Limitations (§7):** new **Representation scope** bullet; new **Store survivorship** bullet (episodes are only self-detected, self-repaired, verifier-gated failures; episode correctness never independently measured; oracle/curated stores are a different treatment) — this replaces the now-obsolete "Ablation store thinness" bullet; new **Multiplicity** bullet; **Fairness notion** bullet rewritten (headline contrast attempt-matched, not token-matched; A1 +22% tokens, 3,506 vs 2,862, stated; token equality only for A1–A2); Corrected-label coverage bullet now states ±8 pts at n = 49 excludes only large effects; Drift bullet updated to the adjusted scoring + operator-mix-as-author-choice; Scope bullet ties the title claim to the tested form on BIRD. Abstract and Contribution 1 no longer claim token-matched fairness for A1−A0 ("attempt-matched protocol with complete/measured token accounting").

## T9 — Secondary-claim re-strengthening — DONE

- A3 flip: abstract drops "manufacturing" (→ "producing"); Contribution 2 reframed ("does not survive corrected labels (0.0 points, ±8)"); §5.2 sensitivity added under T5 with the non-confirmation framing kept.
- Stale-memory neutrality: stated with precision wherever summarized (abstract: 0.0, −5.3…+4.6, 33 silent tasks; §6: "0.0 points on silent tasks, ±5").
- §6 prioritization advice re-earned at reduced strength: "find no support, at this scale, for prioritizing stale-memory invalidation over drift detection… directionally only; a small stale-memory harm remains possible." The "may be misallocated" phrasing is gone.
- Abstract pass^k claim gains the resolution caveat ("at the resolution four runs per task afford"); §5.7 gains the pass⁴ Bernoulli/±5–10 pt caveat.
- §4 Analysis gains the primary-estimand statement (meta-review fix 4): paired run-mean pass@1 difference vs original golds on the 97 primary tasks; corrected view is the pre-committed secondary view on the 49-task L1 subset.
- §5.3 gains the A1/A2 prompt-metadata-difference clause (meta-review fix 4): the A1–A2 contrast is not a pure fingerprint ablation.

## Discrepancies between the brief and the sources (and what was done)

1. **A15 store size:** the brief said "24–28 episodes/run"; the A15 deliverable's own table is 24/23/25/28 per run and its interpretation section says "23–28". The paper uses **23–28** (the deliverable wins).
2. **Replication temperature:** see T7. The code sends temperature 0 for the replication; the paper says so, flagged above.
3. Nothing else was insufficient: all other brief numbers matched their deliverables exactly.

## Verification (final build)

- Pages: **11 total**; bibliography starts **p. 10**; body + appendix ≈ 10 pages ≤ 12 excl. bibliography.
- Greps on the compiled PDF text: "strongest form" = 0; "two implementations" = 0; "15 points on corrected" = 0; "matched token budgets" = 0; "at matched compute" = 0; "A1--A14" = 0; "0.292 corrected" = 0. "−15.4" occurs exactly twice, both times explicitly as the repudiated scoring artifact (§5.4 note, §7).
- Headline numbers unchanged and present: 0.539, 0.521, −1.8 (×4), +9.8 (×4), 0.565, 0.132, $14.91, verifier −8.5/−9.8. New numbers present: 0.363, 0.601, 0.617, 364 of 400, 23–28, −7.5, +5.2, −1.3 (changed-only).
- Title on p. 1 typesets exactly as specified in T1.
- refs.bib untouched.
