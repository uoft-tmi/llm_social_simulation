import pytest

from llm_social_simulation.simulation.gameworld import (
    OpenResourcesAction,
    OpenResourcesConfig,
    OpenResourcesGameWorld,
)


def test_harvest_scales_proportionally_when_resource_insufficient():
    world = OpenResourcesGameWorld(
        OpenResourcesConfig(
            agent_ids=(0, 1),
            initial_resource=10.0,
            max_harvest_per_step=10.0,
            regen_rate=0.0,
        )
    )

    tick = world.apply_actions(
        {
            0: OpenResourcesAction(harvest=10.0, contribute=0.0),
            1: OpenResourcesAction(harvest=10.0, contribute=0.0),
        }
    )

    assert sum(tick.harvest_actual.values()) == pytest.approx(10.0)
    assert tick.harvest_actual[0] == pytest.approx(5.0)
    assert tick.harvest_actual[1] == pytest.approx(5.0)
    assert tick.info["H_act"] == pytest.approx(10.0)
    assert tick.info["allocation_scale"] == pytest.approx(0.5)
    assert tick.info["R_mid"] == pytest.approx(0.0)


def test_contribution_moves_wealth_to_pool_without_rewards():
    world = OpenResourcesGameWorld(
        OpenResourcesConfig(
            agent_ids=(0, 1),
            initial_pool=0.0,
            initial_wealth=10.0,
            governance_reward_rate=0.0,
            regen_rate=0.0,
        )
    )

    tick = world.apply_actions(
        {
            0: OpenResourcesAction(harvest=0.0, contribute=3.0),
            1: OpenResourcesAction(harvest=0.0, contribute=2.0),
        }
    )

    assert tick.P_after == pytest.approx(5.0)
    assert tick.wealth[0] == pytest.approx(7.0)
    assert tick.wealth[1] == pytest.approx(8.0)
    assert tick.reward[0] == pytest.approx(0.0)
    assert tick.reward[1] == pytest.approx(0.0)


def test_resource_regeneration_increases_post_harvest_resource():
    world = OpenResourcesGameWorld(
        OpenResourcesConfig(
            agent_ids=(0, 1),
            initial_resource=50.0,
            resource_cap=100.0,
            regen_rate=0.1,
            regen_mode="linear",
            max_harvest_per_step=10.0,
        )
    )

    tick = world.apply_actions(
        {
            0: OpenResourcesAction(harvest=5.0, contribute=0.0),
            1: OpenResourcesAction(harvest=5.0, contribute=0.0),
        }
    )

    assert tick.R_after > tick.info["R_mid"]
    assert tick.R_after <= 100.0
    assert tick.info["R_mid"] == pytest.approx(tick.R_before - sum(tick.harvest_actual.values()))
