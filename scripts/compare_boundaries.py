import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt

OUTROOT = Path("outputs/phase_open_resources")


def latest_dir_with_tag(tag: str):
    pat = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_" + re.escape(tag) + r"$")
    candidates = [p for p in OUTROOT.iterdir() if p.is_dir() and pat.match(p.name)]
    if not candidates:
        raise RuntimeError(f"No run dirs found for tag='{tag}'")
    return sorted(candidates)[-1]


def extract_boundary(run_dir):
    rows = []
    with open(run_dir / "phase_map.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["y_param"] != "max_harvest_per_step":
                continue
            rows.append(
                {
                    "y_value": float(row["y_value"]),
                    "regen_rate": float(row["regen_rate"]),
                    "collapse_prob": float(row["collapse_prob"]),
                }
            )

    by_h = {}
    for r in rows:
        by_h.setdefault(r["y_value"], []).append(r)

    boundary = []
    for h in sorted(by_h.keys()):
        sub = sorted(by_h[h], key=lambda x: x["regen_rate"])
        for point in sub:
            if point["collapse_prob"] < 1.0:
                boundary.append((h, point["regen_rate"]))
                break

    return boundary


agents = {
    "greedy": "greedy_boundary",
    "coop": "coop_wide",
    "mixed": "mixed_wide",
}

plt.figure(figsize=(7, 6))

for label, tag in agents.items():
    run_dir = latest_dir_with_tag(tag)
    boundary = extract_boundary(run_dir)
    if not boundary:
        continue
    hs = [b[0] for b in boundary]
    rc = [b[1] for b in boundary]
    plt.plot(hs, rc, marker="o", label=label)

plt.xlabel("max_harvest_per_step")
plt.ylabel("critical_regen_rate")
plt.title("Phase boundaries comparison")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()

out_path = OUTROOT / "phase_boundaries_comparison.png"
plt.savefig(out_path, dpi=200)
print("Saved to:", out_path)
