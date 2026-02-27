from __future__ import annotations

import argparse
import csv
import json
import random
import struct
import zlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from llm_social_simulation.simulation.analytics import collapse_time, gini_final_wealth
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld
from llm_social_simulation.simulation.run_open_resources_baseline import _build_agents


def _parse_optional_float(raw: str) -> float | None:
    value = raw.strip().lower()
    if value in {"none", "null"}:
        return None
    return float(raw)


def _parse_agent_types(raw: str) -> list[str]:
    allowed = {"greedy", "coop", "adaptive", "mixed"}
    items = [item.strip() for item in raw.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("agent-types cannot be empty")

    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in allowed:
            raise argparse.ArgumentTypeError(
                "invalid agent type in --agent-types. allowed: greedy,coop,adaptive,mixed"
            )
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _parse_seeds(raw: str) -> list[int]:
    value = raw.strip()
    if not value:
        raise argparse.ArgumentTypeError("seeds cannot be empty")

    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(
                "invalid seeds format. Use 'a:b' or 'a,b,c' (example: 0:30)"
            )
        try:
            start = int(parts[0].strip())
            stop = int(parts[1].strip())
        except ValueError as exc:
            raise argparse.ArgumentTypeError("seeds range must be integers") from exc
        if stop <= start:
            raise argparse.ArgumentTypeError("seeds range requires stop > start")
        return list(range(start, stop))

    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("seeds list cannot be empty")
    try:
        seeds = [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds list must be integers") from exc
    return seeds


def _parse_grid(raw: str) -> list[float]:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "invalid regen-rate-grid format. Use 'start:stop:step' (example: 0.02:0.30:0.02)"
        )
    try:
        start = float(parts[0])
        stop = float(parts[1])
        step = float(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("regen-rate-grid values must be numeric") from exc

    if step <= 0:
        raise argparse.ArgumentTypeError("regen-rate-grid step must be > 0")
    if stop < start:
        raise argparse.ArgumentTypeError("regen-rate-grid requires stop >= start")

    values: list[float] = []
    current = start
    limit = stop + 1e-12
    while current <= limit:
        values.append(round(current, 10))
        current += step

    if not values:
        raise argparse.ArgumentTypeError("regen-rate-grid produced no values")
    return values


def _make_run_dir(outdir: str, tag: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_tag = "_".join(tag.strip().split())
    name = f"{stamp}_{safe_tag}" if safe_tag else stamp
    run_dir = Path(outdir) / name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _trial_metrics(
    *,
    ticks: list[Any],
    config: OpenResourcesConfig,
    agent_type: str,
    seed: int,
    rounds: int,
    regen_rate: float,
) -> dict[str, Any]:
    ct = collapse_time(ticks)
    collapsed = ct is not None

    if ticks:
        final_tick = ticks[-1]
        r_series = [float(tick.R_after) for tick in ticks]
        final_r = float(final_tick.R_after)
        min_r = float(min(r_series))
        avg_r = float(sum(r_series) / len(r_series))
        final_pool = float(final_tick.P_after)
        final_total_wealth = float(sum(float(v) for v in final_tick.wealth.values()))
    else:
        final_r = float(config.initial_resource)
        min_r = float(config.initial_resource)
        avg_r = float(config.initial_resource)
        final_pool = float(config.initial_pool)
        final_total_wealth = float(config.initial_wealth) * len(config.agent_ids)

    return {
        "agent_type": agent_type,
        "seed": int(seed),
        "rounds": int(rounds),
        "rounds_executed": int(len(ticks)),
        "regen_rate": round(float(regen_rate), 10),
        "regen_mode": str(config.regen_mode),
        "n_agents": int(len(config.agent_ids)),
        "initial_resource": float(config.initial_resource),
        "resource_cap": None if config.resource_cap is None else float(config.resource_cap),
        "max_harvest_per_step": float(config.max_harvest_per_step),
        "initial_wealth": float(config.initial_wealth),
        "governance_reward_rate": float(config.governance_reward_rate),
        "reward_mode": str(config.reward_mode),
        "collapse_threshold": float(config.collapse_threshold),
        "collapsed": bool(collapsed),
        "collapse_time": None if ct is None else int(ct),
        "final_R": float(final_r),
        "min_R": float(min_r),
        "avg_R": float(avg_r),
        "final_pool": float(final_pool),
        "final_gini_wealth": float(gini_final_wealth(ticks)),
        "final_total_wealth": float(final_total_wealth),
    }


def _summarize_trials(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        key = (str(trial["agent_type"]), float(trial["regen_rate"]))
        grouped[key].append(trial)

    summary: list[dict[str, Any]] = []
    for agent_type, regen_rate in sorted(grouped.keys(), key=lambda item: (item[0], item[1])):
        group = grouped[(agent_type, regen_rate)]
        collapsed_trials = [trial for trial in group if bool(trial["collapsed"])]
        mean_collapse_time: float | str = (
            fmean(float(trial["collapse_time"]) for trial in collapsed_trials)
            if collapsed_trials
            else ""
        )

        summary.append(
            {
                "agent_type": agent_type,
                "regen_rate": round(float(regen_rate), 10),
                "n_trials": len(group),
                "collapse_prob": fmean(1.0 if trial["collapsed"] else 0.0 for trial in group),
                "mean_collapse_time": mean_collapse_time,
                "mean_final_R": fmean(float(trial["final_R"]) for trial in group),
                "mean_min_R": fmean(float(trial["min_R"]) for trial in group),
                "mean_avg_R": fmean(float(trial["avg_R"]) for trial in group),
                "mean_final_gini_wealth": fmean(
                    float(trial["final_gini_wealth"]) for trial in group
                ),
                "mean_final_total_wealth": fmean(
                    float(trial["final_total_wealth"]) for trial in group
                ),
            }
        )
    return summary


def _write_trials_jsonl(path: Path, trials: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for trial in trials:
            f.write(json.dumps(trial, sort_keys=True))
            f.write("\n")


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "agent_type",
        "regen_rate",
        "n_trials",
        "collapse_prob",
        "mean_collapse_time",
        "mean_final_R",
        "mean_min_R",
        "mean_avg_R",
        "mean_final_gini_wealth",
        "mean_final_total_wealth",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_chunk(f, chunk_type: bytes, data: bytes) -> None:
    f.write(struct.pack("!I", len(data)))
    f.write(chunk_type)
    f.write(data)
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    f.write(struct.pack("!I", crc & 0xFFFFFFFF))


def _set_pixel(
    img: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    idx = (y * width + x) * 3
    img[idx] = color[0]
    img[idx + 1] = color[1]
    img[idx + 2] = color[2]


def _draw_line(
    img: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        _set_pixel(img, width, height, x, y, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _save_simple_plot_png(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    width, height = 800, 500
    margin = 60
    img = bytearray([255] * (width * height * 3))

    black = (0, 0, 0)
    colors = [
        (30, 90, 200),
        (220, 20, 60),
        (20, 140, 80),
        (200, 120, 20),
    ]

    left = margin
    right = width - margin
    top = margin
    bottom = height - margin

    _draw_line(img, width, height, left, bottom, right, bottom, black)
    _draw_line(img, width, height, left, top, left, bottom, black)

    if summary_rows:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in summary_rows:
            grouped[str(row["agent_type"])].append(row)

        all_xs = [float(row["regen_rate"]) for row in summary_rows]
        min_x, max_x = min(all_xs), max(all_xs)

        def map_x(value: float) -> int:
            if max_x == min_x:
                return (left + right) // 2
            ratio = (value - min_x) / (max_x - min_x)
            return int(left + ratio * (right - left))

        def map_y(value: float) -> int:
            clipped = max(0.0, min(1.0, value))
            return int(bottom - clipped * (bottom - top))

        for color_idx, agent_type in enumerate(sorted(grouped.keys())):
            rows = sorted(grouped[agent_type], key=lambda row: float(row["regen_rate"]))
            xs = [float(row["regen_rate"]) for row in rows]
            ys = [float(row["collapse_prob"]) for row in rows]
            points = [(map_x(x), map_y(y)) for x, y in zip(xs, ys, strict=True)]
            line_color = colors[color_idx % len(colors)]
            for idx in range(1, len(points)):
                x0, y0 = points[idx - 1]
                x1, y1 = points[idx]
                _draw_line(img, width, height, x0, y0, x1, y1, line_color)
            for x, y in points:
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        _set_pixel(img, width, height, x + dx, y + dy, line_color)

    raw = bytearray()
    stride = width * 3
    for row in range(height):
        raw.append(0)
        start = row * stride
        raw.extend(img[start : start + stride])

    compressed = zlib.compress(bytes(raw), level=9)

    with path.open("wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
        _write_chunk(f, b"IHDR", ihdr)
        _write_chunk(f, b"IDAT", compressed)
        _write_chunk(f, b"IEND", b"")


def _save_plot(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in summary_rows:
            grouped[str(row["agent_type"])].append(row)
        for agent_type in sorted(grouped.keys()):
            rows = sorted(grouped[agent_type], key=lambda row: float(row["regen_rate"]))
            xs = [float(row["regen_rate"]) for row in rows]
            ys = [float(row["collapse_prob"]) for row in rows]
            ax.plot(xs, ys, marker="o", label=agent_type)
        ax.set_xlabel("regen_rate")
        ax.set_ylabel("collapse probability")
        ax.set_ylim(0.0, 1.0)
        ax.grid(True, alpha=0.3)
        if grouped:
            ax.legend()
        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)
    except Exception:
        _save_simple_plot_png(path, summary_rows)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep Open Resources parameters and aggregate stats."
    )
    parser.add_argument(
        "--agent-type",
        choices=["greedy", "coop", "adaptive", "mixed"],
        default="greedy",
    )
    parser.add_argument(
        "--agent-types",
        type=str,
        default="",
        help="Optional comma list for multi-curve comparison, e.g. greedy,coop,mixed",
    )
    parser.add_argument("--n-agents", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--seeds", type=str, default="0,1,2,3,4")
    parser.add_argument("--initial-resource", type=float, default=60.0)
    parser.add_argument("--resource-cap", type=_parse_optional_float, default=60.0)
    parser.add_argument("--max-harvest-per-step", type=float, default=10.0)
    parser.add_argument("--initial-wealth", type=float, default=10.0)
    parser.add_argument("--regen-mode", choices=["logistic", "linear"], default="logistic")
    parser.add_argument("--governance-reward-rate", type=float, default=0.0)
    parser.add_argument("--reward-mode", choices=["proportional", "equal"], default="proportional")
    parser.add_argument("--collapse-threshold", type=float, default=0.5)
    parser.add_argument("--sweep-param", choices=["regen_rate"], default="regen_rate")
    parser.add_argument("--regen-rate-grid", type=str, default="0.02:0.30:0.02")
    parser.add_argument("--outdir", type=str, default="outputs/sweep_open_resources")
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument(
        "--stop-on-collapse",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Reserved for future parallel execution. Current implementation runs sequentially.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = _parse_args(argv)
    agent_types = (
        _parse_agent_types(args.agent_types)
        if str(args.agent_types).strip()
        else [str(args.agent_type)]
    )
    seeds = _parse_seeds(args.seeds)
    regen_rates = _parse_grid(args.regen_rate_grid)

    run_dir = _make_run_dir(args.outdir, args.tag)
    trials_path = run_dir / "trials.jsonl"
    summary_path = run_dir / "summary.csv"
    config_path = run_dir / "config.json"
    plot_path = run_dir / "plot_collapse_prob.png"

    agent_ids = tuple(range(args.n_agents))
    trials: list[dict[str, Any]] = []

    for agent_type in agent_types:
        for regen_rate in regen_rates:
            for seed in seeds:
                random.seed(seed)
                config = OpenResourcesConfig(
                    agent_ids=agent_ids,
                    initial_resource=float(args.initial_resource),
                    resource_cap=args.resource_cap,
                    initial_wealth=float(args.initial_wealth),
                    max_harvest_per_step=float(args.max_harvest_per_step),
                    regen_rate=float(regen_rate),
                    regen_mode=str(args.regen_mode),
                    governance_reward_rate=float(args.governance_reward_rate),
                    reward_mode=str(args.reward_mode),
                    collapse_threshold=float(args.collapse_threshold),
                )
                world = OpenResourcesGameWorld(config=config)
                agents = _build_agents(agent_type=agent_type, config=config)
                engine = SimulationEngine(world, agents)
                ticks = engine.run(int(args.rounds), stop_on_collapse=bool(args.stop_on_collapse))

                trials.append(
                    _trial_metrics(
                        ticks=ticks,
                        config=config,
                        agent_type=agent_type,
                        seed=int(seed),
                        rounds=int(args.rounds),
                        regen_rate=float(regen_rate),
                    )
                )

    summary_rows = _summarize_trials(trials)
    _write_trials_jsonl(trials_path, trials)
    _write_summary_csv(summary_path, summary_rows)
    _save_plot(plot_path, summary_rows)

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "cli_args": vars(args),
                "resolved": {
                    "agent_types": agent_types,
                    "seeds": seeds,
                    "sweep_values": regen_rates,
                    "run_dir": str(run_dir),
                },
            },
            f,
            indent=2,
            sort_keys=True,
        )

    return run_dir


if __name__ == "__main__":
    out = main()
    print(str(out))
