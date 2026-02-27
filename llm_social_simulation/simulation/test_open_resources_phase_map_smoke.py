import csv
import json

from llm_social_simulation.simulation.run_open_resources_phase_map import main


def test_phase_map_outputs_expected_files_and_grid_shape(tmp_path):
    run_dir = main(
        [
            "--agent-type",
            "greedy",
            "--rounds",
            "40",
            "--seeds",
            "0:3",
            "--regen-rate-grid",
            "0.05:0.06:0.01",
            "--y-param",
            "max_harvest_per_step",
            "--max-harvest-grid",
            "2:4:2",
            "--outdir",
            str(tmp_path / "phase_outputs"),
            "--tag",
            "phase_smoke",
        ]
    )

    trials_path = run_dir / "trials.jsonl"
    phase_map_path = run_dir / "phase_map.csv"
    plot_path = run_dir / "plot_phase_map.png"
    config_path = run_dir / "config.json"

    assert run_dir.exists()
    assert trials_path.exists()
    assert phase_map_path.exists()
    assert plot_path.exists()
    assert config_path.exists()
    assert plot_path.stat().st_size > 0

    trial_lines = trials_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(trial_lines) == 2 * 2 * 3

    with phase_map_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 * 2
    assert set(rows[0].keys()) == {
        "agent_type",
        "y_param",
        "y_value",
        "regen_rate",
        "n_trials",
        "collapse_prob",
        "mean_collapse_time",
    }

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    assert config["resolved"]["seeds"] == [0, 1, 2]
