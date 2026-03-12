from __future__ import annotations

from dataclasses import replace

from llm_social_simulation.api.replay_adapters.open_world import to_open_world_replay_payload
from llm_social_simulation.simulation.open_world.types import OpenWorldAction, OpenWorldObservation
from llm_social_simulation.simulation.open_world.world import OpenWorldConfig, OpenWorldGameWorld


def _world(n_agents: int = 2) -> OpenWorldGameWorld:
    return OpenWorldGameWorld(OpenWorldConfig(agent_ids=tuple(range(n_agents))))


def _resource_band(resource: float, cap: float) -> str:
    frac = 0.0 if cap <= 0.0 else max(0.0, min(1.0, float(resource) / float(cap)))
    if frac <= 0.0:
        return "empty"
    if frac < 0.34:
        return "low"
    if frac < 0.67:
        return "medium"
    return "high"


def _belief(obs: OpenWorldObservation, *, subject_id: int) -> tuple[float, float]:
    item = next(
        entry for entry in obs.reputation_beliefs if int(entry.subject_id) == int(subject_id)
    )
    return float(item.honesty), float(item.confidence)


def test_truthful_resource_report_increases_honesty() -> None:
    world = _world(2)
    zone = world.locations[world.agents[0].location_id]
    true_band = _resource_band(zone.resource, zone.resource_cap)

    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message=f"band:{true_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )
    obs1 = world.get_observation(1)
    honesty, _ = _belief(obs1, subject_id=0)

    assert honesty > 0.5
    assert int(tick.metrics["validated_truthful_reports"]) >= 1


def test_false_resource_report_decreases_honesty() -> None:
    world = _world(2)
    zone = world.locations[world.agents[0].location_id]
    true_band = _resource_band(zone.resource, zone.resource_cap)
    false_band = "low" if true_band != "low" else "high"

    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message=f"band:{false_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )
    obs1 = world.get_observation(1)
    honesty, _ = _belief(obs1, subject_id=0)

    assert honesty < 0.5
    assert int(tick.metrics["validated_false_reports"]) >= 1


def test_beliefs_are_observer_specific_for_local_communication() -> None:
    world = _world(3)
    shared_zone = world.agents[0].location_id
    world.agents[1] = replace(world.agents[1], location_id=shared_zone)
    world.agents[2] = replace(world.agents[2], location_id="sea")
    zone = world.locations[shared_zone]
    true_band = _resource_band(zone.resource, zone.resource_cap)

    world.apply_actions(
        {
            0: OpenWorldAction(
                kind="talk_local",
                message=f"band:{true_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
            2: OpenWorldAction(kind="rest"),
        }
    )

    obs1 = world.get_observation(1)
    obs2 = world.get_observation(2)
    _, confidence_seen = _belief(obs1, subject_id=0)
    assert confidence_seen > 0.0
    assert all(int(item.subject_id) != 0 for item in obs2.reputation_beliefs)


def test_repeated_evidence_increases_confidence() -> None:
    world = _world(2)
    zone = world.locations[world.agents[0].location_id]
    true_band = _resource_band(zone.resource, zone.resource_cap)

    world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message=f"band:{true_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )
    _, confidence_1 = _belief(world.get_observation(1), subject_id=0)

    world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message=f"band:{true_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )
    _, confidence_2 = _belief(world.get_observation(1), subject_id=0)

    assert confidence_2 > confidence_1


def test_replay_and_debug_include_reputation_summaries() -> None:
    world = _world(2)
    zone = world.locations[world.agents[0].location_id]
    true_band = _resource_band(zone.resource, zone.resource_cap)
    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message=f"band:{true_band}",
                speech_act="inform",
                topic="resource_report",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )

    assert "reputation_summary" in tick.info
    summary = dict(tick.info["reputation_summary"])
    assert "by_observer" in summary
    assert "average_honesty_belief" in summary

    replay = to_open_world_replay_payload(
        run_id="run_reputation_test",
        ticks=[tick],
        summary={
            "params": {"agent_type": "rule"},
            "final_agents": {
                str(agent_id): {"credits": float(agent.wealth)}
                for agent_id, agent in world.agents.items()
            },
        },
    )
    replay_tick = replay["ticks"][0]
    assert "reputation" in replay_tick
    assert "averageHonestyBelief" in replay_tick["metrics"]
    assert "averageBeliefConfidence" in replay_tick["metrics"]
