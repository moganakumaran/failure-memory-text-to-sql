#!/usr/bin/env python3
"""Figure 1 for Paper #1: paired pass@1 differences with bootstrap 95% CIs.
Original-label contrasts from pilot_stage1/2_results.json; corrected-label
contrasts as reported in the Stage 2 report (same analysis run)."""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (label, diff_pts, lo, hi) — top to bottom in plot order
repeated_orig = [
    ("A1 − A0  (fingerprinted memory)", -1.8, -5.7, 2.1),
    ("A2 − A0  (generic memory)", -4.6, -9.5, 0.0),
    ("A2 − A1", -2.8, -7.7, 1.6),
    ("A3 − A0  (generate-and-select)", 9.8, 4.1, 16.0),
    ("A3 − A1", 11.6, 5.7, 18.0),
]
repeated_corr = [
    ("A1 − A0", -1.0, -6.1, 4.1),
    ("A2 − A0", -4.6, -10.7, 1.0),
    ("A3 − A0", 0.0, -8.2, 8.2),
    ("A3 − A1", 1.0, -7.7, 10.2),
]
drift = [
    ("A1 − A0  (live memory)", -4.6, -9.6, 0.4),
    ("A4 − A0  (stale memory)", -1.7, -6.3, 2.9),
    ("A4 − A0  (silent drift only)", 0.0, -5.3, 4.6),
    ("A4 − A1  (stale vs live)", 2.9, -2.1, 7.9),
]
# Replication contrasts from hidden_files/pilot_rep_results.json
# (diffs in points; CIs x100 from proportions). A2/drift not replicated.
rep_orig = [
    ("A1 − A0  (failure memory)", 0.0, -4.6, 4.6),
    ("A3 − A0  (generate-and-select)", 0.8, -6.4, 8.3),
    ("A3 − A1", 0.8, -8.0, 9.5),
]
rep_corr = [
    ("A1 − A0", 3.1, 0.0, 8.2),
    ("A3 − A0", 4.1, -4.1, 12.2),
    ("A3 − A1", 1.0, -8.2, 10.2),
]

groups = [
    ("Repeated-failure split — original labels (n = 97)", repeated_orig),
    ("Repeated-failure split — corrected labels (n = 49)", repeated_corr),
    ("Drift split — original labels (n = 60; silent subset n = 33)", drift),
    ("Replication (Qwen2.5-Coder-32B) — original labels (n = 97)", rep_orig),
    ("Replication (Qwen2.5-Coder-32B) — corrected labels (n = 49)", rep_corr),
]

rows = []          # (y, label, diff, lo, hi, is_group_header)
y = 0
for title, items in groups:
    rows.append((y, title, None, None, None, True)); y += 1
    for lab, d, lo, hi in items:
        rows.append((y, "   " + lab, d, lo, hi, False)); y += 1
    y += 0.6

fig, ax = plt.subplots(figsize=(8.6, 0.42 * y + 0.8))
for yy, lab, d, lo, hi, hdr in rows:
    if hdr:
        ax.text(-23.8, yy, lab, fontsize=9.5, fontweight="bold", va="center")
    else:
        ax.errorbar(d, yy, xerr=[[d - lo], [hi - d]], fmt="o", ms=4.5,
                    color="#1a5276", ecolor="#5d8aa8", elinewidth=1.4, capsize=3)
        ax.text(-23.8, yy, lab, fontsize=9, va="center")
        ax.text(19.8, yy, f"{d:+.1f}  [{lo:+.1f}, {hi:+.1f}]", fontsize=8.5, va="center")

ax.axvline(0, color="#888", lw=1)
ax.axvline(12, color="#c0392b", lw=1, ls="--")
ax.text(12, y - 0.4, " GO margin (+12)", color="#c0392b", fontsize=8, rotation=0)
ax.set_xlim(-24, 27)
ax.set_ylim(y - 0.2, -1.2)
ax.set_yticks([])
ax.set_xlabel("Paired difference in pass@1 (percentage points), bootstrap 95% CI")
ax.set_title("Paper #1 pilot: paired pass@1 differences by arm contrast and label view",
             fontsize=10.5)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
out = pathlib.Path(__file__).resolve().parent / "Paper 1 Figure 1 - Paired Differences.png"
fig.savefig(out, dpi=200)
print("wrote", out)
