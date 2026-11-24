# Paper #1 Critique Fixes — Results Memo

> **Correction note (added 2026-11-23, PVLDB minimum viable revision):** the corrected-label paired drift effect reported in §F1 below (−15.4 pts, "significant") was later shown to be a **scoring artifact** and is superseded. It executed Jin et al.'s corrected SQL — written against the original schemas — unadjusted on the drifted databases, where it fails to execute at all on 22 of 23 rename tasks, so corrected passes on the drifted side were mechanically false. Re-scored with drift-adjusted corrected golds (Amendment-era analysis A6; see `mvr_analysis6_drift_rescoring.md` in this directory), the corrected paired drift effect is **−8.3 pts (−17.5…+0.4, n.s.)**, identical to the original-label effect. The original-label numbers and all other sections of this memo are unaffected. The memo text below is preserved as the record of the analysis as run.

**Date:** 2026-11-23. **Scope:** the fix package approved after the reviewer-style critique of Draft v1 (Protocol Amendment A14). Runs: gpt-5-mini-2025-08-07, same harness/scoring as the pilot; analysis `hidden_files/analysis_a14.py` → `a14_results.json`, plus offline analyses `hidden_files/analysis_fixes.py` → `fixes_results.json`. Total A14 spend: $2.81 (ledger $17.84 of the $24 cap). Each section maps to the critique item it resolves (file: "Paper 1 Reviewer Critique - Draft v1 - 2026-11-23.md").

## F1 — The paired drift effect (was: FATAL)

The draft compared A0 across two different splits (0.539 repeated vs 0.308 drift). The control run — A0 on the original databases for exactly the 60 drift tasks, 4 runs, 240 trajectories — gives the paired contrast on identical tasks:

| View | A0 undrifted | A0 drifted | Paired drift effect (95% CI) |
|---|---|---|---|
| Original labels | 0.392 | 0.308 | **−8.3 pts (−18.3…+1.7)**, n.s. |
| Corrected labels | 0.446 | 0.292 | **−15.4 pts (−27.1…−4.2)**, significant |

**What the paper must now say:** the drift tasks are intrinsically harder (undrifted A0 is 0.392, not 0.539), so most of the draft's "53.9% → 30.8%" gap was task difficulty, not drift. The true paired drift effect is ≈8 points on original labels (not significant at n=60) and ≈15 points on corrected labels (significant). "Drift halves accuracy" is deleted everywhere; the Abstract and §6 are rewritten to the paired numbers. The stale-memory neutrality result (A4−A0 within the drifted condition) is unaffected. §6's conclusion survives in weakened form: drift is a real but moderate accuracy cost, and still not a memory-poisoning effect.

## M8 — Verifier ablation (was: MAJOR)

Arms A0/A1 on the repeated split with the self-verifier disabled, 4 runs, 1,600 trajectories. Two findings, one expected and one not:

1. **The verifier is a net harm, not a hidden helper.** Removing it *raises* A0 from 0.539 to **0.624** and A1 from 0.521 to **0.619**. Paired verifier effect (on − off): A0 **−8.5 pts (−14.2…−3.4)**, A1 **−9.8 pts (−15.7…−4.1)** — the self-verifier damages more correct answers (via REVISE) than it rescues, in both arms. The reviewer's confound — "the verifier already does memory's job" — is refuted in the strongest way: the verifier was doing negative work.
2. **The memory null persists without the verifier:** A1−A0 = **−0.5 pts (−3.9…+2.6)** original labels; +2.0 (−4.1…+8.2) corrected. *Stated caveat:* the ablation's A1 store was thin — 2–3 episodes per run (vs ~25/run in the main study), retrieval in only 18/100 S2 trajectories — because in this architecture acquisition is verifier-coupled: without verifier rejections, the only acquisition events are execution-error recoveries (11 in 400 S1 trajectories; mini fails mostly silently). So the ablation cleanly answers the verifier question, but as a memory test it is weak by construction. That coupling is itself a reportable design finding: memory acquisition that depends on verifier signals inherits the verifier's fragility. The paper should present the ablation under exactly this framing.

## M9 — pass^k, the frozen claim's own metric (was: MAJOR; free, offline)

τ-bench estimator C(c,k)/C(n,k) from the existing 4 runs/task. A1−A0 paired differences:

| Study | pass^2 | pass^4 |
|---|---|---|
| Mini, original labels | −2.2 (−7.6…+3.1) | −3.1 (−10.3…+4.1) |
| Mini, corrected labels | −3.7 (−11.9…+4.4) | −6.1 (−18.4…+6.1) |
| Qwen replication, original | +0.3 (−4.6…+5.0) | **0.0 (−5.2…+5.2)** |

The null holds at every k — and in the replication it is exact at pass^4 as well as pass@1. A small pass^k table goes into §5. (Side observation: Qwen's pass^4 of 0.567 barely drops from its pass@1 of 0.583 — near-deterministic at temperature 0 — while mini degrades 0.539 → 0.443.)

## M5 — A1's fingerprint path barely fired (was: MAJOR; free, offline)

From the trace retrieval metadata (fingerprint-path entries are those produced by post-error `retrieve_fingerprint`):

| Study | S2 trajectories with any retrieval | With a fingerprint-path hit | Episodes via fingerprint / total |
|---|---|---|---|
| Mini A1 | 364/400 | **9/400** | 35 / 808 (4.3%) |
| Qwen A1 | 184/400 | 13/400 | 13 / 260 (5.0%) |
| Mini A2 (control) | 373/400 | 0 (by design) | 0 / 786 |

The reviewer's suspicion is confirmed quantitatively: ~96% of A1's retrieved episodes arrived through the same embedding path A2 uses, because the exact class+signature+schema-overlap fingerprint match is too strict to fire. **§5.3's framing must change:** the study did not test two fully distinct designs; it tested embedding-retrieved episodic memory with and without a rarely-active fingerprint fast-path. The mechanism finding — fingerprint keying at this strictness is nearly inert — is itself worth reporting, and it bounds what the null says about fingerprint designs in general.

## M6 — Drift-arm acquisition counts (was: part of MAJOR; free, offline)

- A4's frozen pre-drift stores held **22 / 17 / 16 / 19 episodes** (runs 1–4) — not empty; the stale-memory null cannot be dismissed as an empty store.
- A1 acquired **72 further episodes during the drift phase** (its store was live, as designed).
- A4 acquired **0** during the drift phase (frozen, as designed).

## M2 — Acquisition denominator (writing fix, confirmed by the data)

Qwen Session-1: 237 failed trajectories, of which 205 were agent-observed failures (execution error or verifier rejection) and 32 were silent failures the agent never detected. Acquisition rate = 27/205 = 0.132. §5.5 is corrected to state both numbers.

## Status of the critique after A14

- **Resolved with new data:** F1 (paired drift effect), M8 (verifier confound — refuted, plus a new finding), M9 (pass^k), M5 (fingerprint firing rate; framing change required), M6-partial (drift acquisition counts; A13 disclosure and embedding naming remain writing/release tasks), M2 (denominator).
- **Resolved by the 2026-11-23 deep-research verification:** M7 related work (Reflexion, ExpeL, Generative Agents, MAC-SQL, DIN-SQL — all verified on primary sources) and the CHASE-SQL claim, which must be corrected from "only verified multi-agent win" to "highest reported BIRD execution accuracy among multi-agent Text-to-SQL systems at its time"; m5 reference completions (Jin et al.'s exact title; DABstep preprint status; DataAgentBench citation).
- **Still open (author decisions / writing):** M3 abstract alignment, M4 title scope (or the optional frontier run), M1 drift-scoring wording, m1–m10 minors, artefact/protocol release mechanics.

**Net assessment:** the revision is stronger than the draft it fixes. The paper gains a paired drift estimate, a refuted confound with a bonus finding (a harmful self-verifier), pass^k numbers for its own frozen metric, and a mechanism result (inert fingerprinting). Nothing in A14 weakens the central claim; two of the draft's supporting claims (drift magnitude, two-designs framing) shrink to what the data actually show.
