#!/usr/bin/env python3
"""Figure 2 for Paper #1: drift-split composition.
Counts read directly from hidden_files/drift_spec.csv (60 rows):
operator x drift_type cross-tab verified 2026-11-23 —
rename 23 overt, type-change 4 overt (= 27 overt);
recode 10, unit 9, merge 9, temporal 4, null 1, all silent (= 33 silent).
Matches Draft v1 section 3.2 exactly."""
import csv, pathlib
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

spec = pathlib.Path(__file__).resolve().parent / "drift_spec.csv"
rows = list(csv.DictReader(open(spec)))
assert len(rows) == 60, len(rows)
ct = Counter((r["operator"], r["drift_type"]) for r in rows)

labels = [
    ("Column rename", "schema_column_rename"),
    ("Value recode", "data_value_recode"),
    ("Unit change", "data_unit_change"),
    ("Category merge", "category_merge"),
    ("Temporal grain", "temporal_grain_change"),
    ("Type change", "schema_type_change"),
    ("Null semantics", "null_semantics_change"),
]
silent, overt, names = [], [], []
for name, op in labels:
    names.append(name)
    silent.append(ct.get((op, "silent"), 0))
    overt.append(ct.get((op, "overt"), 0))
assert sum(silent) == 33 and sum(overt) == 27, (sum(silent), sum(overt))

fig, ax = plt.subplots(figsize=(8.6, 4.2))
y = range(len(names))
ax.barh(list(y), silent, color="#1a5276", label="Silent (meaning changes, names unchanged) — 33")
ax.barh(list(y), overt, left=silent, color="#c0392b", label="Overt (rename / type change) — 27")
for i, (s, o) in enumerate(zip(silent, overt)):
    if s:
        ax.text(s / 2, i, str(s), ha="center", va="center", color="white", fontsize=9)
    if o:
        ax.text(s + o / 2, i, str(o), ha="center", va="center", color="white", fontsize=9)
ax.set_yticks(list(y))
ax.set_yticklabels(names, fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("Drifted tasks (n = 60, all L1 corrected-label tasks)")
ax.set_title("Paper #1 drift split: 60 execution-verified variants by operator",
             fontsize=10.5)
ax.legend(loc="lower right", fontsize=8.5)
ax.set_xlim(0, 27)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
out = pathlib.Path(__file__).resolve().parent / "Paper 1 Figure 2 - Drift Split.png"
fig.savefig(out, dpi=200)
print("wrote", out, "| silent", sum(silent), "overt", sum(overt))
