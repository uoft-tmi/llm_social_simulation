from __future__ import annotations

import argparse
import csv
import json
import random
import struct
import zlib
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from llm_social_simulation.simulation.analytics import collapse_time
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld
from llm_social_simulation.simulation.run_open_resources_baseline import _build_agents


def _parse_optional_float(raw: str) -> float | None:
    value = raw.strip().lower()
    if value in {"none", "null"}:
        return None
    return float(raw)


def _parse_seeds(raw: str) -> list[int]:
    value = raw.strip()
    if not value:
        raise argparse.ArgumentTypeError("seeds cannot be empty")
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("invalid seeds format. Use 'a:b' or 'a,b,c'")
        try:
            start = int(parts[0].strip())
            stop = int(parts[1].strip())
        except ValueError as exc:
            raise argparse.ArgumentTypeError("seed range values must be integers") from exc
        if stop <= start:
            raise argparse.ArgumentTypeError("seed range requires stop > start")
        return list(range(start, stop))

    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("seeds list cannot be empty")
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds list must be integers") from exc


def _parse_float_grid(raw: str) -> list[float]:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("invalid grid format. Use 'start:stop:step'")
    try:
        start = float(parts[0])
        stop = float(parts[1])
        step = float(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid values must be numeric") from exc
    if step <= 0:
        raise argparse.ArgumentTypeError("grid step must be > 0")
    if stop < start:
        raise argparse.ArgumentTypeError("grid requires stop >= start")

    values: list[float] = []
    cur = start
    while cur <= stop + 1e-12:
        values.append(round(cur, 10))
        cur += step
    return values


def _parse_int_grid(raw: str) -> list[int]:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("invalid int grid format. Use 'start:stop:step'")
    try:
        start = int(parts[0])
        stop = int(parts[1])
        step = int(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("int grid values must be integers") from exc
    if step <= 0:
        raise argparse.ArgumentTypeError("int grid step must be > 0")
    if stop < start:
        raise argparse.ArgumentTypeError("int grid requires stop >= start")

    return list(range(start, stop + 1, step))


def _make_run_dir(outdir: str, tag: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_tag = "_".join(tag.strip().split())
    name = f"{stamp}_{safe_tag}" if safe_tag else stamp
    run_dir = Path(outdir) / name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_chunk(f, chunk_type: bytes, data: bytes) -> None:
    f.write(struct.pack("!I", len(data)))
    f.write(chunk_type)
    f.write(data)
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    f.write(struct.pack("!I", crc & 0xFFFFFFFF))


def _set_pixel(img: bytearray, width: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    idx = (y * width + x) * 3
    img[idx] = color[0]
    img[idx + 1] = color[1]
    img[idx + 2] = color[2]


def _color_for_prob(p: float) -> tuple[int, int, int]:
    prob = max(0.0, min(1.0, float(p)))
    r = int(255 * prob)
    g = int(200 * (1.0 - abs(prob - 0.5) * 2))
    b = int(255 * (1.0 - prob))
    return (r, g, b)


def _save_heatmap_fallback(path: Path, matrix: list[list[float]]) -> None:
    rows = max(1, len(matrix))
    cols = max(1, len(matrix[0]) if matrix else 1)
    cell = 32
    width = cols * cell
    height = rows * cell
    img = bytearray([255] * (width * height * 3))

    for r in range(rows):
        for c in range(cols):
            p = float(matrix[r][c]) if matrix else 0.0
            color = _color_for_prob(p)
            for y in range(r * cell, (r + 1) * cell):
                for x in range(c * cell, (c + 1) * cell):
                    _set_pixel(img, width, x, y, color)

    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(img[start : start + stride])

    with path.open("wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
        _write_chunk(f, b"IHDR", ihdr)
        _write_chunk(f, b"IDAT", zlib.compress(bytes(raw), level=9))
        _write_chunk(f, b"IEND", b"")


def _save_heatmap_plot(
    *,
    path: Path,
    matrix: list[list[float]],
    x_values: list[float],
    y_values: list[float | int],
    y_param: str,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 5))
        im = ax.imshow(matrix, origin="lower", aspect="auto", vmin=0.0, vmax=1.0, cmap="viridis")
        ax.set_xlabel("regen_rate")
        ax.set_ylabel(y_param)
        ax.set_xticks(range(len(x_values)))
        ax.set_xticklabels([f"{x:.2f}" for x in x_values], rotation=45, ha="right")
        ax.set_yticks(range(len(y_values)))
        ax.set_yticklabels([str(v) for v in y_values])
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("collapse_prob")
        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)
    except Exception:
        _save_heatmap_fallback(path, matrix)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 2D phase diagram for Open Resources.")
    parser.add_argument(
        "--agent-type",
        choices=["greedy", "coop", "adaptive", "mixed", "llm"],
        default="greedy",
    )
    parser.add_argument(
        "--llm-guardrails",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--llm-model", type=str, default="openai/gpt-4o-mini")
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--llm-max-tokens", type=int, default=160)
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
    parser.add_argument("--regen-rate-grid", type=str, default="0.02:0.30:0.02")
    parser.add_argument(
        "--y-param",
        choices=["max_harvest_per_step", "n_agents"],
        default="max_harvest_per_step",
    )
    parser.add_argument("--max-harvest-grid", type=str, default="2:20:2")
    parser.add_argument("--n-agents-grid", type=str, default="4:12:2")
    parser.add_argument("--outdir", type=str, default="outputs/phase_open_resources")
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument(
        "--stop-on-collapse",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--max-workers", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = _parse_args(argv)
    seeds = _parse_seeds(args.seeds)
    x_values = _parse_float_grid(args.regen_rate_grid)
    if args.y_param == "max_harvest_per_step":
        y_values: list[float | int] = _parse_float_grid(args.max_harvest_grid)
    else:
        y_values = _parse_int_grid(args.n_agents_grid)

    run_dir = _make_run_dir(args.outdir, args.tag)
    trials_path = run_dir / "trials.jsonl"
    phase_map_path = run_dir / "phase_map.csv"
    plot_path = run_dir / "plot_phase_map.png"
    config_path = run_dir / "config.json"

    trials: list[dict[str, Any]] = []

    with trials_path.open("w", encoding="utf-8") as f:
        for y in y_values:
            for regen_rate in x_values:
                for seed in seeds:
                    random.seed(seed)
                    n_agents = int(y) if args.y_param == "n_agents" else int(args.n_agents)
                    max_harvest = (
                        float(y)
                        if args.y_param == "max_harvest_per_step"
                        else float(args.max_harvest_per_step)
                    )
                    config = OpenResourcesConfig(
                        agent_ids=tuple(range(n_agents)),
                        initial_resource=float(args.initial_resource),
                        resource_cap=args.resource_cap,
                        initial_wealth=float(args.initial_wealth),
                        max_harvest_per_step=max_harvest,
                        regen_rate=float(regen_rate),
                        regen_mode=str(args.regen_mode),
                        governance_reward_rate=float(args.governance_reward_rate),
                        reward_mode=str(args.reward_mode),
                        collapse_threshold=float(args.collapse_threshold),
                    )
                    world = OpenResourcesGameWorld(config=config)
                    agents = _build_agents(
                        agent_type=args.agent_type,
                        config=config,
                        llm_guardrails=bool(args.llm_guardrails),
                        llm_model=str(args.llm_model),
                        llm_temperature=float(args.llm_temperature),
                        llm_max_tokens=int(args.llm_max_tokens),
                    )
                    engine = SimulationEngine(world, agents)
                    ticks = engine.run(
                        int(args.rounds),
                        stop_on_collapse=bool(args.stop_on_collapse),
                    )

                    ct = collapse_time(ticks)
                    trial = {
                        "agent_type": args.agent_type,
                        "seed": int(seed),
                        "regen_rate": round(float(regen_rate), 10),
                        "y_param": args.y_param,
                        "y_value": int(y) if args.y_param == "n_agents" else float(y),
                        "collapsed": bool(ct is not None),
                        "collapse_time": None if ct is None else int(ct),
                        "rounds_executed": len(ticks),
                    }
                    trials.append(trial)
                    f.write(json.dumps(trial, sort_keys=True))
                    f.write("\n")

    grouped: dict[tuple[float, float | int], list[dict[str, Any]]] = {}
    for trial in trials:
        key = (float(trial["regen_rate"]), trial["y_value"])
        grouped.setdefault(key, []).append(trial)

    matrix: list[list[float]] = []
    with phase_map_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "agent_type",
                "y_param",
                "y_value",
                "regen_rate",
                "n_trials",
                "collapse_prob",
                "mean_collapse_time",
            ],
        )
        writer.writeheader()
        for y in y_values:
            row_probs: list[float] = []
            for regen_rate in x_values:
                key = (float(regen_rate), y)
                cell_trials = grouped.get(key, [])
                collapsed = [t for t in cell_trials if bool(t["collapsed"])]
                collapse_prob = (
                    fmean(1.0 if t["collapsed"] else 0.0 for t in cell_trials)
                    if cell_trials
                    else 0.0
                )
                row_probs.append(float(collapse_prob))
                mean_ct: float | str = (
                    fmean(float(t["collapse_time"]) for t in collapsed) if collapsed else ""
                )
                writer.writerow(
                    {
                        "agent_type": args.agent_type,
                        "y_param": args.y_param,
                        "y_value": y,
                        "regen_rate": round(float(regen_rate), 10),
                        "n_trials": len(cell_trials),
                        "collapse_prob": collapse_prob,
                        "mean_collapse_time": mean_ct,
                    }
                )
            matrix.append(row_probs)

    _save_heatmap_plot(
        path=plot_path,
        matrix=matrix,
        x_values=x_values,
        y_values=y_values,
        y_param=str(args.y_param),
    )

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "cli_args": vars(args),
                "resolved": {
                    "seeds": seeds,
                    "regen_rate_values": x_values,
                    "y_values": y_values,
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
