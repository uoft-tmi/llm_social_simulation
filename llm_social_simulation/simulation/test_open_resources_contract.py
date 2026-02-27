from llm_social_simulation.simulation.gameworld import (
    OpenResourcesAction,
    OpenResourcesConfig,
    OpenResourcesGameWorld,
    OpenResourcesObservation,
    OpenResourcesTick,
)


def _world() -> OpenResourcesGameWorld:
    config = OpenResourcesConfig(
        agent_ids=(0, 1),
        initial_resource=50.0,
        initial_pool=3.0,
        initial_wealth=10.0,
        max_harvest_per_step=5.0,
    )
    return OpenResourcesGameWorld(config=config)


def test_open_resources_instantiation_works():
    world = _world()

    assert world.state.t == 0
    assert world.state.R == 50.0
    assert world.state.P == 3.0
    assert world.state.wealth == {0: 10.0, 1: 10.0}


def test_get_observation_contract_shape():
    world = _world()

    obs = world.get_observation(0)

    assert isinstance(obs, OpenResourcesObservation)
    assert obs.self_id == 0
    assert obs.t == 0
    assert obs.R == 50.0
    assert obs.P == 3.0
    assert obs.self_wealth == 10.0
    assert obs.known_agents == [0, 1]
    assert "contract_only" in obs.info
    assert obs.info["max_harvest_per_step"] == 5.0
    assert obs.info["resource_cap"] == 50.0
    assert obs.info["last_step_self"] is None


def test_apply_actions_returns_contract_complete_tick():
    world = _world()

    tick = world.apply_actions(
        {
            0: OpenResourcesAction(harvest=2.0, contribute=1.0),
            1: OpenResourcesAction(harvest=1.0, contribute=0.5),
        }
    )

    assert isinstance(tick, OpenResourcesTick)
    required_fields = {
        "t",
        "R_before",
        "R_after",
        "P_before",
        "P_after",
        "harvest_requested",
        "harvest_actual",
        "contribute",
        "reward",
        "wealth",
        "clamped",
        "info",
    }

    assert required_fields.issubset(set(tick.__dataclass_fields__.keys()))
    assert tick.t == 0
    assert set(tick.harvest_requested.keys()) == {0, 1}
    assert set(tick.harvest_actual.keys()) == {0, 1}
    assert set(tick.contribute.keys()) == {0, 1}
    assert set(tick.reward.keys()) == {0, 1}
    assert set(tick.wealth.keys()) == {0, 1}
    assert set(tick.clamped.keys()) == {0, 1}
    assert "effective_regen_rate" in tick.info
    assert "contrib_ratio" in tick.info


def test_apply_actions_clamps_invalid_values_and_sets_flags():
    world = _world()

    tick = world.apply_actions(
        {
            0: OpenResourcesAction(harvest=-2.0, contribute=100.0),
            1: OpenResourcesAction(harvest=999.0, contribute=-3.0),
        }
    )

    assert tick.harvest_requested[0] == 0.0
    assert tick.contribute[0] == 10.0
    assert tick.clamped[0]["harvest"] is True
    assert tick.clamped[0]["contribute"] is True

    assert tick.harvest_requested[1] == 5.0
    assert tick.contribute[1] == 0.0
    assert tick.clamped[1]["harvest"] is True
    assert tick.clamped[1]["contribute"] is True


def test_observation_includes_last_step_feedback_after_first_tick():
    world = _world()

    world.apply_actions(
        {
            0: OpenResourcesAction(harvest=2.0, contribute=1.0),
            1: OpenResourcesAction(harvest=1.0, contribute=0.5),
        }
    )
    obs = world.get_observation(0)

    assert obs.t == 1
    assert isinstance(obs.info["last_step_self"], dict)
    assert obs.info["last_step_self"]["t"] == 0
    assert obs.info["last_step_self"]["harvest_requested"] == 2.0
    assert "clamped" in obs.info["last_step_self"]
