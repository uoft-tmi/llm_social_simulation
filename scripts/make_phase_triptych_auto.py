from __future__ import annotations

import re
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

OUTROOT = Path("outputs/phase_open_resources")


def latest_dir_with_tag(tag: str) -> Path:
    # Match directories like: 2026-02-27_040359_greedy_wide
    pat = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_" + re.escape(tag) + r"$")
    candidates = [p for p in OUTROOT.iterdir() if p.is_dir() and pat.match(p.name)]
    if not candidates:
        raise SystemExit(f"No run dirs found for tag='{tag}' under {OUTROOT}")
    return sorted(candidates)[-1]


tags = ["greedy_wide", "coop_wide", "mixed_wide"]
dirs = {t: latest_dir_with_tag(t) for t in tags}

paths = [
    ("greedy", dirs["greedy_wide"] / "plot_phase_map.png"),
    ("coop", dirs["coop_wide"] / "plot_phase_map.png"),
    ("mixed", dirs["mixed_wide"] / "plot_phase_map.png"),
]

for title, p in paths:
    if not p.exists():
        raise SystemExit(f"Missing image for {title}: {p}")

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for ax, (title, p) in zip(axes, paths, strict=True):
    img = mpimg.imread(p)
    ax.imshow(img)
    ax.set_title(f"{title}\\n{p.parent.name}", fontsize=10)
    ax.axis("off")

out_path = OUTROOT / "phase_triptych.png"
fig.tight_layout()
fig.savefig(out_path, dpi=200)
print(out_path)
