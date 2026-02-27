import csv
import json

from llm_social_simulation.simulation.agents_rule_based import GreedyHarvesterAgent
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld
from llm_social_simulation.simulation.run_open_resources_sweep import main


def test_sweep_smoke_outputs_expected_files_and_shapes(tmp_path):
    outdir = tmp_path / "sweep_outputs"
    run_dir = main(
        [
            "--agent-type",
            "greedy",
            "--n-agents",
            "4",
            "--rounds",
            "50",
            "--seeds",
            "0:3",
            "--regen-rate-grid",
            "0.05:0.06:0.01",
            "--outdir",
            str(outdir),
            "--tag",
            "smoke",
        ]
    )

    trials_path = run_dir / "trials.jsonl"
    summary_path = run_dir / "summary.csv"
    config_path = run_dir / "config.json"
    plot_path = run_dir / "plot_collapse_prob.png"

    assert run_dir.exists()
    assert trials_path.exists()
    assert summary_path.exists()
    assert config_path.exists()
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0

    trials_lines = trials_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(trials_lines) == 2 * 3

    with summary_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert set(rows[0].keys()) == {
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
    }

    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    assert cfg["resolved"]["seeds"] == [0, 1, 2]


def test_engine_stop_on_collapse_stops_early():
    config = OpenResourcesConfig(
        agent_ids=(0,),
        initial_resource=1.0,
        resource_cap=1.0,
        regen_rate=0.0,
        collapse_threshold=0.9,
        max_harvest_per_step=10.0,
    )

    world_fast_stop = OpenResourcesGameWorld(config)
    agents_fast_stop = [GreedyHarvesterAgent(agent_id=0, max_harvest_per_step=10.0)]
    engine_fast_stop = SimulationEngine(world_fast_stop, agents_fast_stop)
    history_fast_stop = engine_fast_stop.run(rounds=20, stop_on_collapse=True)

    world_full = OpenResourcesGameWorld(config)
    agents_full = [GreedyHarvesterAgent(agent_id=0, max_harvest_per_step=10.0)]
    engine_full = SimulationEngine(world_full, agents_full)
    history_full = engine_full.run(rounds=20, stop_on_collapse=False)

    assert len(history_fast_stop) < 20
    assert len(history_full) == 20


def test_sweep_supports_multi_agent_type_comparison(tmp_path):
    run_dir = main(
        [
            "--agent-types",
            "greedy,coop,mixed",
            "--n-agents",
            "4",
            "--rounds",
            "30",
            "--seeds",
            "0:2",
            "--regen-rate-grid",
            "0.05:0.06:0.01",
            "--outdir",
            str(tmp_path / "cmp_outputs"),
            "--tag",
            "compare",
        ]
    )

    trials_path = run_dir / "trials.jsonl"
    summary_path = run_dir / "summary.csv"
    plot_path = run_dir / "plot_collapse_prob.png"

    trial_lines = trials_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(trial_lines) == 3 * 2 * 2

    with summary_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3 * 2
    assert {row["agent_type"] for row in rows} == {"greedy", "coop", "mixed"}

    assert plot_path.exists()
    assert plot_path.stat().st_size > 0
