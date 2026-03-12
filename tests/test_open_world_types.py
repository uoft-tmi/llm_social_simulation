from __future__ import annotations

import json

import pytest

from llm_social_simulation.simulation.open_world.types import (
    AgentState,
    LocationState,
    OpenWorldAction,
    OpenWorldEvent,
    OpenWorldObservation,
    OpenWorldTick,
)


def _sample_world_state() -> tuple[LocationState, LocationState, AgentState, AgentState]:
    village = LocationState(
        id="village",
        resource=2.0,
        resource_cap=5.0,
        regen_rate=0.1,
        neighbors=("forest",),
    )
    forest = LocationState(
        id="forest",
        resource=8.0,
        resource_cap=10.0,
        regen_rate=0.25,
        neighbors=("village",),
    )
    self_agent = AgentState(
        id=1,
        location_id="village",
        inventory={"wood": 1.0},
        energy=9.0,
        wealth=3.0,
        persona_tag="forager",
    )
    nearby_agent = AgentState(
        id=2,
        location_id="forest",
        inventory={},
        energy=8.0,
        wealth=1.0,
        persona_tag="trader",
    )
    return village, forest, self_agent, nearby_agent


def test_open_world_schema_instantiation_works() -> None:
    village, forest, self_agent, nearby_agent = _sample_world_state()
    action = OpenWorldAction(kind="move", move_target="forest")
    event = OpenWorldEvent(
        t=0,
        agent_id=1,
        kind="move",
        location_id="village",
        action=action,
        valid=True,
        reason="heading to forest to gather",
    )
    obs = OpenWorldObservation(
        self_id=1,
        t=0,
        self_state=self_agent,
        location=village,
        nearby_locations=(forest,),
        nearby_agents=(nearby_agent,),
        recent_events=(event,),
        action_space={"move_targets": ["forest"], "can_gather": True, "can_rest": True},
    )
    tick = OpenWorldTick(
        t=0,
        locations={"village": village, "forest": forest},
        agents={1: self_agent, 2: nearby_agent},
        events=(event,),
        metrics={"gather_total": 0.0, "move_total": 1, "collapse": False},
        info={"mode": "open_world"},
    )

    assert obs.self_id == 1
    assert tick.t == 0
    assert event.kind == "move"


def test_open_world_schema_serialization_round_trip() -> None:
    village, forest, self_agent, nearby_agent = _sample_world_state()
    gather_action = OpenWorldAction(kind="gather", gather_resource="wood", amount=1.0)
    event = OpenWorldEvent(
        t=2,
        agent_id=1,
        kind="gather",
        location_id="forest",
        action=gather_action,
        valid=True,
        reason="gather wood",
        payload={"actual_amount": 1.0},
    )
    tick = OpenWorldTick(
        t=2,
        locations={"village": village, "forest": forest},
        agents={
            1: AgentState(
                id=1,
                location_id="forest",
                inventory={"wood": 2.0},
                energy=7.5,
                wealth=4.0,
                last_action=gather_action,
            ),
            2: nearby_agent,
        },
        events=(event,),
        metrics={"gather_total": 1.0, "move_total": 0, "collapse": False},
    )

    as_dict = tick.to_dict()
    payload = json.dumps(as_dict)
    decoded = json.loads(payload)
    restored = OpenWorldTick.from_dict(decoded)

    assert restored.to_dict() == tick.to_dict()


def test_open_world_observation_serialization_round_trip() -> None:
    village, forest, self_agent, nearby_agent = _sample_world_state()
    event = OpenWorldEvent(
        t=0,
        agent_id=2,
        kind="rest",
        location_id="forest",
        action=OpenWorldAction(kind="rest"),
        valid=True,
        reason="recover energy",
    )
    obs = OpenWorldObservation(
        self_id=1,
        t=3,
        self_state=self_agent,
        location=village,
        nearby_locations=(forest,),
        nearby_agents=(nearby_agent,),
        recent_events=(event,),
        action_space={"move_targets": ["forest"], "can_gather": True, "can_rest": True},
        info={"weather": "clear"},
    )

    as_dict = obs.to_dict()
    payload = json.dumps(as_dict)
    decoded = json.loads(payload)
    restored = OpenWorldObservation.from_dict(decoded)
    assert restored.to_dict() == obs.to_dict()


def test_local_observation_rejects_far_away_information() -> None:
    village, forest, self_agent, _ = _sample_world_state()
    far_agent = AgentState(
        id=99,
        location_id="mountain",
        inventory={},
        energy=5.0,
        wealth=1.0,
    )

    with pytest.raises(ValueError, match="far-away agent"):
        OpenWorldObservation(
            self_id=1,
            t=0,
            self_state=self_agent,
            location=village,
            nearby_locations=(forest,),
            nearby_agents=(far_agent,),
            action_space={"move_targets": ["forest"]},
        )


def test_invalid_move_target_is_rejected() -> None:
    village, forest, self_agent, nearby_agent = _sample_world_state()
    obs = OpenWorldObservation(
        self_id=1,
        t=1,
        self_state=self_agent,
        location=village,
        nearby_locations=(forest,),
        nearby_agents=(nearby_agent,),
        action_space={"move_targets": ["forest"]},
    )

    obs.validate_action(OpenWorldAction(kind="move", move_target="forest"))
    with pytest.raises(ValueError, match="Invalid move target"):
        obs.validate_action(OpenWorldAction(kind="move", move_target="mountain"))
