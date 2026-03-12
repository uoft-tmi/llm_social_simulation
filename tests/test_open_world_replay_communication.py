from __future__ import annotations

import json

from llm_social_simulation.api.replay_adapters.open_world import to_open_world_replay_payload
from llm_social_simulation.simulation.open_world.types import OpenWorldAction
from llm_social_simulation.simulation.open_world.world import OpenWorldConfig, OpenWorldGameWorld


def test_replay_includes_structured_communication_entries() -> None:
    world = OpenWorldGameWorld(OpenWorldConfig(agent_ids=(0,)))
    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="talk_local",
                message="local update",
                speech_act="inform",
                topic="status",
            )
        }
    )

    replay = to_open_world_replay_payload(
        run_id="run_comm_test",
        ticks=[tick],
        summary={
            "params": {"agent_type": "rule"},
            "final_agents": {"0": {"credits": float(world.agents[0].wealth)}},
        },
    )
    first_tick = replay["ticks"][0]
    communications = first_tick["communications"]

    assert len(communications) == 1
    assert communications[0]["scope"] == "local"
    assert communications[0]["message"] == "local update"
    assert communications[0]["speechAct"] == "inform"
    assert communications[0]["topic"] == "status"
    assert "reputation" in first_tick
    assert "decisionInfluence" in first_tick
    assert "averageHonestyBelief" in first_tick["metrics"]
    assert "averageBeliefConfidence" in first_tick["metrics"]
    assert "communicationInfluencedActionTotal" in first_tick["metrics"]
    assert "trustedInfluenceActionTotal" in first_tick["metrics"]
    assert "suspiciousDiscountActionTotal" in first_tick["metrics"]
    json.dumps(replay)
