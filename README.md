# Failure Memory Does Not Help Text-to-SQL Agents

**A Compute-Fair, Corrected-Label Evaluation**

Mogana Kumaran Sivaraman — Independent Researcher, San Francisco, CA, USA

Status: manuscript in preparation for arXiv (cs.DB) and PVLDB submission. This repository is the public reproducibility package for the paper: frozen protocol, harness and analysis code, task splits, full run traces, and results.

## What the paper shows

Episodic memory of past failures is widely assumed to help LLM agents. We test that assumption for Text-to-SQL agents under the conditions the claim requires: a pre-registered protocol, paired comparisons at matched token budgets, and scoring against both original BIRD labels and independently audited corrected labels (Jin et al.).

Headline results (paired pass@1, 97 primary tasks, 4 runs per task per arm):

| Contrast | Original labels | Corrected labels |
|---|---|---|
| Fingerprinted memory (A1) − no memory (A0) | −1.8 pts (95% CI −5.7…+2.1) | −1.0 pt |
| Generic episodic memory (A2) − A0 | −4.6 pts (−9.5…0.0) | −4.6 pts |
| Generate-and-select (A3) − A0 | +9.8 pts (+4.1…+16.0) | 0.0 pts (−8.2…+8.2) |
| Replication on Qwen2.5-Coder-32B: A1 − A0 | exactly 0.0 pts (−4.6…+4.6) | +3.1 pts |
| Paired drift effect (same 60 tasks, A0) | −8.3 pts (−18.3…+1.7) | −15.4 pts (−27.1…−4.2) |
| Stale (frozen) memory under silent drift: A4 − A0 | exactly 0.0 pts | — |

Memory acquisition was healthy (100 episodes from 177 observed failures, rate 0.565), so the null is not an empty-store artifact. A verifier ablation further shows the base agent's self-verifier is a net harm (−8.5 to −9.8 points) and that the memory null persists without it.

## Repository layout

- `paper/` — the manuscript (named and anonymous Markdown), figures.
- `protocol/` — the frozen pilot protocol v2 with dated amendments A1–A14, the substrate specification (task selection and corrected-label policy), and the power analysis that set the split sizes and the +12-point GO margin.
- `code/` — the experiment harness (`pilot.py`, `pilot_lib.py`), split/drift builders, dry runs, analysis scripts, and figure scripts. `code/README-code.md` maps each file to the paper section it supports.
- `data/` — the frozen task splits (`splits_repeated.csv`, `drift_spec.csv`) and the task manifest (`manifest_v2.csv`). The BIRD benchmark itself is **not** redistributed; see `data/README-data.md` for how to obtain BIRD and the corrected labels.
- `traces/` — the complete run record: per-trajectory traces and episode journals for the main study, the open-model replication, the drift split, and the verifier ablation.
- `results/` — machine-readable analysis outputs (paired pass@1 with bootstrap intervals, pass^k, ablation and drift contrasts) and the study reports they were drawn from.

## Reproducing the analysis

The analysis scripts run offline against the released traces and results JSONs (Python 3, standard library; `matplotlib` only for the figure scripts):

```
python3 code/analysis_stage1.py   # Stage 1: A0 vs A1, repeated split
python3 code/analysis_stage2.py   # Stage 2: A2, A3, drift
python3 code/analysis_rep.py      # Open-model replication
python3 code/analysis_a14.py      # Paired drift control + verifier ablation
```

Re-running the experiments themselves requires API access to the pinned models (gpt-5-mini-2025-08-07 via OpenAI; Qwen2.5-Coder-32B-Instruct via OpenRouter) and the BIRD databases, rebuilt with `code/build_splits.py` and `code/build_drift.py`. All runs were executed under pre-set budget caps recorded in the protocol amendments.

## License

Code is released under the MIT License (see `LICENSE`). Paper text, protocol documents, and figures are © the author, released for scholarly use with attribution. Third-party data (BIRD; Jin et al.'s corrected labels, CC-BY-SA-4.0) remain under their original licenses and are not redistributed here.

## Citation

```bibtex
@article{sivaraman2026failurememory,
  title   = {Failure Memory Does Not Help Text-to-SQL Agents:
             A Compute-Fair, Corrected-Label Evaluation},
  author  = {Sivaraman, Mogana Kumaran},
  journal = {arXiv preprint},
  year    = {2026},
  note    = {arXiv ID to be inserted on announcement}
}
```
