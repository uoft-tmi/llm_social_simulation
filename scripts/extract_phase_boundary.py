import csv
from pathlib import Path

import matplotlib.pyplot as plt

RUN_DIR = Path("outputs/phase_open_resources/2026-02-27_041803_greedy_boundary")
OUT_PATH = RUN_DIR / "critical_boundary.png"

csv_path = RUN_DIR / "phase_map.csv"

rows = []

with open(csv_path, newline="") as f:
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
    h = r["y_value"]
    by_h.setdefault(h, []).append(r)

boundary = []

for h in sorted(by_h.keys()):
    sub = sorted(by_h[h], key=lambda x: x["regen_rate"])

    r_crit = None
    for point in sub:
        if point["collapse_prob"] < 1.0:
            r_crit = point["regen_rate"]
            break

    if r_crit is not None:
        boundary.append((h, r_crit))

if not boundary:
    raise RuntimeError("No stable region found; boundary cannot be extracted.")

hs = [b[0] for b in boundary]
rc = [b[1] for b in boundary]

plt.figure(figsize=(6, 5))
plt.plot(hs, rc, marker="o")
plt.xlabel("max_harvest_per_step")
plt.ylabel("critical_regen_rate")
plt.title("Phase boundary (greedy)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_PATH, dpi=200)

print(OUT_PATH)
