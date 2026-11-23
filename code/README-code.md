# Paper #1 — Code

Code for: **"Failure Memory Does Not Help Text-to-SQL Agents: A Compute-Fair,
Corrected-Label Evaluation"** (Mogana Kumaran Sivaraman, Draft v2, 2026-11-23).
This repository contains only the code. The manuscript, protocol, traces,
results, and datasets live in the companion project repository.

## Files

**Experiment harness**
- `pilot_lib.py` — model backends (OpenAI / OpenRouter / Ollama), budget
  ledger with hard cap, read-only SQL execution, embeddings, and the
  `EpisodeStore` that enforces the paper's no-gold memory-acquisition policy
  (§3.4) in code.
- `pilot.py` — the base agent and arms A0–A4 (§3.3): no memory, fingerprinted
  memory, generic memory, generate-and-select, stale memory; drift and
  undrifted-control modes; `--no-verifier` ablation mode (§5.6).

**Substrate construction**
- `build_manifest.py` — task manifest with label status (L1–L4, §3.1).
- `build_splits.py` — the repeated-failure split (§3.2).
- `build_drift.py`, `build_drift_lib.py`, `fix_drift_silent.py` — the drift
  split: 60 execution-verified drifted database variants, 55% silent (§3.2).

**Dry runs (taxonomy + base rates)**
- `dry_run.py` (local Qwen2.5-Coder-3B), `dry_run_frontier.py` (GPT-5),
  `dry_run_mini.py` (GPT-5 mini), `dry_run_or.py` (Qwen2.5-Coder-32B via
  OpenRouter) — the four dry runs behind the frozen failure taxonomy (§3.5).

**Analysis (every number in the paper)**
- `power_analysis.py` — simulation-based power analysis (§4).
- `analysis_stage1.py` — Stage 1: A0 vs A1, repeated split (§5.1).
- `analysis_stage2.py` — Stage 2: A3 (§5.2), A2 (§5.3), drift (§5.4).
- `analysis_rep.py` — open-model replication (§5.5).
- `analysis_a14.py` — Amendment A14: paired drift control (§5.4) and verifier
  ablation (§5.6).
- `analysis_fixes.py` — offline analyses: pass^k (§5.7), fingerprint retrieval
  rates (§5.3), drift-arm acquisition counts.
- `make_figure1.py`, `make_figure2.py` — the paper's figures.

All paired contrasts use per-task run-mean pass@1 with task-level bootstrap
95% CIs (10,000 resamples, seed 20261122).

## Layout, inputs, dependencies

Paths are portable: every script resolves its project root as the directory
containing the code (`Path(__file__).parent`). The builders and dry runs
expect the study layout under that root — `hidden_files/datasets/` (BIRD Dev
and the Jin et al. corrected-label repo), `hidden_files/manifest_v1.csv`, and
outputs written under `hidden_files/`. The pilot harness (`pilot_lib.py`)
expects `datasets/` beside the code. The analysis scripts read the run traces
(`traces_*.jsonl`), episode journals, splits (`splits_repeated.csv`),
`manifest_v2.csv` and `drift_spec.csv` from the same directory; those data
artefacts are **not** in this repository — they live, with the manuscript,
protocol and reports, in the companion private repository
`github.com/moganakumaran/agentic-ai-research-papers`. `make_figure2.py`
needs `drift_spec.csv` beside the code; `make_figure1.py` is self-contained
(contrast values embedded, as reported).

Dependencies: Python 3 standard library plus `matplotlib` (figures only).
Model access is not via an SDK: the OpenAI and OpenRouter backends shell out
to connector helper scripts — set `OPENAI_HELPER` / `OPENROUTER_HELPER` to
their paths (defaults preserve the original study machine's locations); the
local backend expects an Ollama server on localhost. API credentials are held
by those helpers, never by this code.

Note: the code was patched for path portability after the study ran
(2026-11-23, with the author's approval); the patch changed no logic, and the
figure scripts were re-run after patching and reproduce the paper's figures
byte-identically.
