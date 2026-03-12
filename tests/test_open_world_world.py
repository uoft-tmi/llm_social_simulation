from __future__ import annotations

from dataclasses import replace

import pytest

from llm_social_simulation.simulation.open_world.types import OpenWorldAction
from llm_social_simulation.simulation.open_world.world import OpenWorldConfig, OpenWorldGameWorld


def _world(n_agents: int = 1) -> OpenWorldGameWorld:
    return OpenWorldGameWorld(OpenWorldConfig(agent_ids=tuple(range(n_agents))))


def test_move_updates_agent_position() -> None:
    world = _world(1)
    start = world.agents[0].location_id
    obs = world.get_observation(0)
    destination = obs.move_targets[0]

    tick = world.apply_actions({0: OpenWorldAction(kind="move", move_target=destination)})

    assert world.agents[0].location_id == destination
    assert any(e.kind == "move" and e.agent_id == 0 for e in tick.events)
    assert start != destination


def test_invalid_move_creates_invalid_action_event() -> None:
    world = _world(1)
    start = world.agents[0].location_id

    tick = world.apply_actions({0: OpenWorldAction(kind="move", move_target="unknown_zone")})

    assert world.agents[0].location_id == start
    assert any(e.kind == "invalid_action" and e.agent_id == 0 for e in tick.events)
    assert int(tick.metrics["invalid_action_total"]) >= 1


def test_gather_transfers_resource_to_inventory() -> None:
    world = _world(1)
    agent = world.agents[0]
    zone_id = agent.location_id
    zone = world.locations[zone_id]
    resource_type = str(zone.meta["resource_type"])
    before_resource = float(zone.resource)
    before_inventory = float(agent.inventory.get(resource_type, 0.0))

    action = OpenWorldAction(kind="gather", gather_resource=resource_type, amount=3.0)
    tick = world.apply_actions({0: action})
    gather_event = next(e for e in tick.events if e.agent_id == 0 and e.kind == "gather")
    gathered = float(gather_event.payload["actual"])

    after_agent = world.agents[0]
    after_zone = world.locations[zone_id]
    expected_after_resource = min(
        float(zone.resource_cap),
        before_resource - gathered + float(zone.regen_rate),
    )

    assert after_agent.inventory[resource_type] == pytest.approx(before_inventory + gathered)
    assert after_zone.resource == pytest.approx(expected_after_resource)


def test_rest_restores_energy() -> None:
    world = _world(1)
    obs = world.get_observation(0)
    destination = obs.move_targets[0]

    world.apply_actions({0: OpenWorldAction(kind="move", move_target=destination)})
    energy_after_move = float(world.agents[0].energy)
    world.apply_actions({0: OpenWorldAction(kind="rest")})
    energy_after_rest = float(world.agents[0].energy)

    assert energy_after_rest > energy_after_move
    assert energy_after_rest <= float(world.config.max_energy)


def test_resources_regenerate_each_tick() -> None:
    world = _world(1)
    zone_id = world.agents[0].location_id
    resource_type = str(world.locations[zone_id].meta["resource_type"])

    world.apply_actions(
        {0: OpenWorldAction(kind="gather", gather_resource=resource_type, amount=4.0)}
    )
    after_gather = float(world.locations[zone_id].resource)
    world.apply_actions({0: OpenWorldAction(kind="rest")})
    after_regen = float(world.locations[zone_id].resource)

    assert after_regen >= after_gather
    assert after_regen <= float(world.locations[zone_id].resource_cap)


def test_observations_are_local_scope_only() -> None:
    world = _world(3)
    obs = world.get_observation(0)

    current_id = world.agents[0].location_id
    neighbor_ids = set(world.locations[current_id].neighbors)
    visible_ids = neighbor_ids | {current_id}
    all_zone_ids = set(world.locations.keys())
    far_zone_ids = all_zone_ids - visible_ids

    assert {loc.id for loc in obs.nearby_locations} == neighbor_ids
    assert all(agent.location_id in visible_ids for agent in obs.nearby_agents)
    assert all(event.location_id in visible_ids for event in obs.recent_events)
    assert all(loc.id not in far_zone_ids for loc in obs.nearby_locations)


def test_empty_communication_is_rejected_as_invalid_action() -> None:
    world = _world(1)

    tick = world.apply_actions(
        {
            0: {
                "kind": "talk_local",
                "message": "   ",
            }
        }
    )

    assert any(event.kind == "invalid_action" and event.agent_id == 0 for event in tick.events)
    assert int(tick.metrics["invalid_action_total"]) >= 1


def test_talk_local_visibility_is_isolated_to_same_zone() -> None:
    world = _world(3)
    location_id = world.agents[0].location_id
    world.agents[1] = replace(world.agents[1], location_id=location_id)
    far_zone = next(zone for zone in world.locations if zone != location_id)
    world.agents[2] = replace(world.agents[2], location_id=far_zone)

    world.apply_actions(
        {
            0: OpenWorldAction(
                kind="talk_local",
                message="local status update",
                speech_act="inform",
                topic="status",
            ),
            1: OpenWorldAction(kind="rest"),
            2: OpenWorldAction(kind="rest"),
        }
    )

    obs_same_zone = world.get_observation(1)
    obs_far = world.get_observation(2)
    assert any(
        comm.message == "local status update" for comm in obs_same_zone.recent_communications
    )
    assert all(comm.message != "local status update" for comm in obs_far.recent_communications)


def test_public_bulletin_visibility_is_global() -> None:
    world = _world(2)

    world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message="global bulletin",
                speech_act="warn",
                topic="safety",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )

    obs0 = world.get_observation(0)
    obs1 = world.get_observation(1)
    assert any(comm.message == "global bulletin" for comm in obs0.public_bulletins)
    assert any(comm.message == "global bulletin" for comm in obs1.public_bulletins)
