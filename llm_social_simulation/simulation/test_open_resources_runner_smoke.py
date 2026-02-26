from llm_social_simulation.simulation.run_open_resources_baseline import run_baseline_experiment


def test_runner_returns_expected_shapes_for_greedy():
    ticks, summary = run_baseline_experiment(
        agent_type="greedy",
        n_agents=4,
        rounds=10,
        seed=0,
        config_overrides={
            "regen_rate": 0.0,
            "max_harvest_per_step": 10.0,
            "initial_resource": 20.0,
        },
    )

    assert len(ticks) == 10
    assert isinstance(summary["final_R"], float)
    assert set(summary["final_wealth"].keys()) == {0, 1, 2, 3}
    assert 0.0 <= summary["gini_final"] <= 1.0


def test_greedy_depletes_more_than_coop_under_low_regen():
    common_overrides = {
        "regen_rate": 0.01,
        "initial_resource": 50.0,
        "resource_cap": 50.0,
        "max_harvest_per_step": 10.0,
        "initial_wealth": 10.0,
    }

    _, greedy_summary = run_baseline_experiment(
        agent_type="greedy",
        n_agents=4,
        rounds=30,
        seed=0,
        config_overrides=common_overrides,
    )
    _, coop_summary = run_baseline_experiment(
        agent_type="coop",
        n_agents=4,
        rounds=30,
        seed=0,
        config_overrides=common_overrides,
    )

    assert greedy_summary["final_R"] <= coop_summary["final_R"]
