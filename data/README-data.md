# Data

This study uses the **BIRD** benchmark (dev split, `dev_20240627`) and the corrected labels released by **Jin et al.** Neither is redistributed in this repository.

## What is included here

- `splits_repeated.csv` — the frozen repeated-failure split: 100 Session-1/Session-2 task pairs (seed 20261122), with per-pair similarity distances; 3 near-duplicate pairs are flagged as recall controls and excluded from the primary metric (97 primary Session-2 tasks).
- `drift_spec.csv` — the frozen drift split specification: 60 tasks with drift operator, drift type (33 silent / 27 overt), drifted database path, and drift-adjusted gold SQL.
- `manifest_v2.csv` — the frozen task manifest with label-policy classes (L1 corrected available: 498 tasks; L2 original-only: 1,035; L3 disputed: 1) and split assignments.

## Obtaining the underlying data

1. **BIRD dev**: download from the official BIRD site (bird-bench.github.io). The file used here is `dev.zip`, SHA256 `cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630` (1,534 tasks, 11 databases).
2. **Corrected labels**: Jin et al., "Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards" (arXiv:2601.08778); correction repository released under CC-BY-SA-4.0 (498 BIRD Dev entries: 220 corrected, 278 audited-unchanged).
3. **Drifted databases**: rebuildable from the original BIRD databases with `code/build_drift.py` driven by `drift_spec.csv`.
