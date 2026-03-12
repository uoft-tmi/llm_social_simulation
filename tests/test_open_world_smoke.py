from __future__ import annotations

import json

from llm_social_simulation.simulation.open_world.runner import run_open_world_baseline


def test_open_world_smoke_runs_4_agents_for_8_ticks() -> None:
    ticks, summary = run_open_world_baseline(n_agents=4, rounds=8, seed=0)

    assert len(ticks) == 8
    assert summary["mode"] == "open_world"
    assert summary["ticks_executed"] == 8
    assert set(summary["final_agents"].keys()) == {"0", "1", "2", "3"}
    assert all(len(tick.events) >= 4 for tick in ticks)
    assert all("total_resource" in tick.metrics for tick in ticks)

    # replay-friendly payload check
    json.dumps(ticks[-1].to_dict())


def test_open_world_smoke_runs_5_agents_for_6_ticks() -> None:
    ticks, summary = run_open_world_baseline(n_agents=5, rounds=6, seed=1)

    assert len(ticks) == 6
    assert summary["ticks_executed"] == 6
    assert len(summary["final_agents"]) == 5
    assert summary["final_total_credits"] >= 0.0
