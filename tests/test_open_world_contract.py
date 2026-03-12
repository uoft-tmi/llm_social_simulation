from __future__ import annotations

import pytest

from llm_social_simulation.simulation.open_world.types import (
    AgentState,
    LocationState,
    OpenWorldAction,
    OpenWorldEvent,
    OpenWorldObservation,
    OpenWorldTick,
)


def test_open_world_schema_fields_are_explicit_and_stable() -> None:
    assert set(LocationState.__dataclass_fields__.keys()) == {
        "id",
        "resource",
        "resource_cap",
        "regen_rate",
        "neighbors",
        "blocked",
        "meta",
    }
    assert set(AgentState.__dataclass_fields__.keys()) == {
        "id",
        "location_id",
        "inventory",
        "energy",
        "wealth",
        "persona_tag",
        "memory_summary",
        "last_action",
        "meta",
    }
    assert set(OpenWorldObservation.__dataclass_fields__.keys()) == {
        "self_id",
        "t",
        "self_state",
        "location",
        "nearby_locations",
        "nearby_agents",
        "recent_events",
        "action_space",
        "info",
    }
    assert set(OpenWorldAction.__dataclass_fields__.keys()) == {
        "kind",
        "move_target",
        "gather_resource",
        "amount",
        "meta",
    }
    assert set(OpenWorldEvent.__dataclass_fields__.keys()) == {
        "t",
        "agent_id",
        "kind",
        "location_id",
        "action",
        "valid",
        "reason",
        "payload",
    }
    assert set(OpenWorldTick.__dataclass_fields__.keys()) == {
        "t",
        "locations",
        "agents",
        "events",
        "metrics",
        "info",
    }


def test_open_world_action_contract_is_strict() -> None:
    with pytest.raises(ValueError, match="Unsupported action kind"):
        OpenWorldAction(kind="teleport")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="move_target"):
        OpenWorldAction(kind="move")

    with pytest.raises(ValueError, match="move_target must be None for gather action"):
        OpenWorldAction(kind="gather", move_target="forest")

    with pytest.raises(ValueError, match="amount must be None for rest action"):
        OpenWorldAction(kind="rest", amount=1.0)


def test_invalid_events_are_clearly_marked() -> None:
    event = OpenWorldEvent(
        t=1,
        agent_id=3,
        kind="invalid_action",
        location_id="village",
        valid=True,  # constructor coerces this to False for invalid_action
        reason="target not adjacent",
    )
    assert event.valid is False
    assert event.to_dict()["valid"] is False

    with pytest.raises(ValueError, match="Invalid events must include a reason"):
        OpenWorldEvent(
            t=1,
            agent_id=3,
            kind="invalid_action",
            location_id="village",
            valid=False,
            reason=None,
        )


def test_tick_contract_rejects_unknown_agent_location() -> None:
    village = LocationState(
        id="village",
        resource=2.0,
        resource_cap=5.0,
        regen_rate=0.1,
        neighbors=("forest",),
    )
    off_map_agent = AgentState(
        id=7,
        location_id="mountain",
        inventory={},
        energy=5.0,
        wealth=2.0,
    )

    with pytest.raises(ValueError, match="unknown location_id"):
        OpenWorldTick(
            t=0,
            locations={"village": village},
            agents={7: off_map_agent},
            events=(),
            metrics={},
        )
