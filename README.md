# Episodic Failure Memory Does Not Help Text-to-SQL Agents

**A Compute-Fair, Corrected-Label Evaluation on BIRD**

Mogana Kumaran Sivaraman — Independent Researcher, San Francisco, CA, USA

Status: revised manuscript prepared for PVLDB submission (VLDB 2027, Experiment, Analysis & Benchmark track); an earlier version was prepared for arXiv (cs.DB). This repository is the public reproducibility package for the paper: frozen protocol, harness and analysis code, task splits, full run traces, and results.

## What the paper shows

Episodic memory of past failures is widely assumed to help LLM agents. We test that assumption for Text-to-SQL agents under the conditions the claim requires: a pre-registered protocol, paired comparisons under an attempt-matched protocol with complete token accounting, and scoring against both original BIRD labels and independently audited corrected labels (Jin et al.). The memory tested is embedding-retrieved raw episodic traces of the agent's own verified self-repairs, in two variants of one retrieval design (a failure-fingerprint fast path, which fired in only 9 of 400 Session-2 trajectories, over generic embedding retrieval).

Headline results (paired pass@1, 97 primary tasks, 4 runs per task per arm):

| Contrast | Original labels | Corrected labels |
|---|---|---|
| Episodic memory, fingerprint variant (A1) − no memory (A0) | −1.8 pts (95% CI −5.7…+2.1) | −1.0 pt |
| Episodic memory, generic variant (A2) − A0 | −4.6 pts (−9.5…0.0) | −4.6 pts |
| Generate-and-select (A3) − A0 | +9.8 pts (+4.1…+16.0) | 0.0 pts (−8.2…+8.2) |
| Replication on Qwen2.5-Coder-32B: A1 − A0 | exactly 0.0 pts (−4.6…+4.6) | +3.1 pts |
| Paired drift effect (same 60 tasks, A0) | −8.3 pts (−18.3…+1.7) | −8.3 pts (−17.5…+0.4), drift-adjusted golds |
| Stale (frozen) memory under silent drift: A4 − A0 | exactly 0.0 pts | +1.5 pts (−3.8…+6.1), drift-adjusted |
| Store-transplant ablation (A15): A1-T − A0, verifier off, full store | −2.3 pts (−6.4…+1.6) | +2.0 pts |

Memory acquisition was healthy (100 episodes from 177 observed failures, rate 0.565), so the null is not an empty-store artifact. A verifier ablation further shows the base agent's self-verifier is a net harm (−8.5 to −9.8 points) and that the memory null persists without it — including, per Amendment A15, when the verifier-off agent is given a full transplanted store (23–28 episodes per run), so store size was not the binding constraint.

**Correction (PVLDB revision, 2026-11-23):** an earlier version of this package reported the corrected-label paired drift effect as −15.4 points. That figure was a scoring artifact: it executed Jin et al.'s corrected SQL — written against the original schemas — unadjusted on the drifted databases, where it fails to execute at all on 22 of 23 rename tasks, making corrected passes mechanically false. Re-scored with drift-adjusted corrected golds (`data/mvr_drift_adjusted_corrected_golds.jsonl`; `results/mvr_analysis6_drift_rescoring.md`), the corrected drift effect is −8.3 points, identical to the original-label effect. The −15.4 figure survives in the revised paper only as the explicitly repudiated artifact.

## Repository layout

- `paper/` — the revised manuscript (PVLDB format: `manuscript-pvldb.pdf`, LaTeX source `manuscript-pvldb.tex` + `refs.bib`) and figures. The pre-revision arXiv manuscripts were removed in the revision sync; they remain in this repository's git history.
- `protocol/` — the frozen pilot protocol v2 with dated amendments A1–A15, the substrate specification (task selection and corrected-label policy), and the power analysis that set the split sizes and the +12-point GO margin.
- `code/` — the experiment harness (`pilot.py`, `pilot_lib.py`), split/drift builders, dry runs, analysis scripts (including the A15 transplant run and the revision re-scoring scripts), and figure scripts. `code/README-code.md` maps each file to the paper section it supports.
- `data/` — the frozen task splits (`splits_repeated.csv`, `drift_spec.csv`), the task manifest (`manifest_v2.csv`), and the drift-adjusted corrected golds used for the revision's corrected-label drift scoring (`mvr_drift_adjusted_corrected_golds.jsonl`). The BIRD benchmark itself is **not** redistributed; see `data/README-data.md` for how to obtain BIRD and the corrected labels.
- `traces/` — the complete run record: per-trajectory traces and episode journals for the main study, the open-model replication, the drift split, the verifier ablation, and the A15 store-transplant ablation.
- `results/` — machine-readable analysis outputs (paired pass@1 with bootstrap intervals, pass^k, ablation and drift contrasts), the study reports they were drawn from, and the PVLDB revision analyses (changed-gold accounting, drift-adjusted re-scoring, A15 transplant results, the B-02 subset re-analysis of §5.2, revision notes).

## Reproducing the analysis

The analysis scripts run offline against the released traces and results JSONs (Python 3, standard library; `matplotlib` only for the figure scripts):

```
python3 code/analysis_stage1.py   # Stage 1: A0 vs A1, repeated split
python3 code/analysis_stage2.py   # Stage 2: A2, A3, drift
python3 code/analysis_rep.py      # Open-model replication
python3 code/analysis_a14.py      # Paired drift control + verifier ablation
python3 code/analysis_a15.py      # A15 store-transplant ablation (§5.6)
python3 code/mvr_analysis5_changed_gold.py  # Revision: changed-gold accounting (§3.1, §5.1–5.2)
python3 code/mvr_analysis6_rescore.py       # Revision: drift-adjusted corrected re-scoring (§5.4)
```

Re-running the experiments themselves requires API access to the pinned models (gpt-5-mini-2025-08-07 via OpenAI; Qwen2.5-Coder-32B-Instruct via OpenRouter) and the BIRD databases, rebuilt with `code/build_splits.py` and `code/build_drift.py`. All runs were executed under pre-set budget caps recorded in the protocol amendments.

## License

Code is released under the MIT License (see `LICENSE`). Paper text, protocol documents, and figures are © the author, released for scholarly use with attribution. Third-party data (BIRD; Jin et al.'s corrected labels, CC-BY-SA-4.0) remain under their original licenses and are not redistributed here.

## Citation

```bibtex
@article{sivaraman2026failurememory,
  title   = {Episodic Failure Memory Does Not Help Text-to-SQL Agents:
             A Compute-Fair, Corrected-Label Evaluation on BIRD},
  author  = {Sivaraman, Mogana Kumaran},
  journal = {arXiv preprint},
  year    = {2026},
  note    = {arXiv ID to be inserted on announcement}
}
```
