from __future__ import annotations

from llm_social_simulation.agents.open_world.rule_based import DeterministicOpenWorldAgent
from llm_social_simulation.simulation.open_world.types import (
    AgentState,
    LocationState,
    OpenWorldCommunication,
    OpenWorldObservation,
    ReputationBelief,
)


def _observation(
    *,
    energy: float,
    current_resource: float,
    neighbor_resources: dict[str, float],
    public_bulletins: tuple[OpenWorldCommunication, ...] = (),
    reputation_beliefs: tuple[ReputationBelief, ...] = (),
) -> OpenWorldObservation:
    current = LocationState(
        id="housing",
        resource=current_resource,
        resource_cap=20.0,
        regen_rate=0.5,
        neighbors=tuple(neighbor_resources.keys()),
        meta={"resource_type": "labor"},
    )
    nearby_locations = tuple(
        LocationState(
            id=zone_id,
            resource=value,
            resource_cap=20.0,
            regen_rate=0.5,
            neighbors=(),
            meta={"resource_type": "resource", "coarse": True},
        )
        for zone_id, value in neighbor_resources.items()
    )
    self_state = AgentState(
        id=0,
        location_id="housing",
        inventory={},
        energy=energy,
        wealth=0.0,
    )
    return OpenWorldObservation(
        self_id=0,
        t=0,
        self_state=self_state,
        location=current,
        nearby_locations=nearby_locations,
        nearby_agents=(),
        recent_events=(),
        public_bulletins=public_bulletins,
        reputation_beliefs=reputation_beliefs,
        action_space={
            "move_targets": list(neighbor_resources.keys()),
            "can_gather": True,
            "can_rest": True,
        },
    )


def test_rule_based_rests_when_energy_low() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0)
    obs = _observation(energy=2.5, current_resource=10.0, neighbor_resources={"forest": 9.0})

    action = agent.decide(obs)
    assert action.kind == "rest"


def test_rule_based_gathers_when_current_zone_has_resource() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0, gather_amount=1.5)
    obs = _observation(energy=8.0, current_resource=4.0, neighbor_resources={"forest": 8.0})

    action = agent.decide(obs)
    assert action.kind == "gather"
    assert action.gather_resource == "labor"
    assert action.amount == 1.5


def test_rule_based_moves_to_better_neighbor() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0)
    obs = _observation(
        energy=8.0,
        current_resource=0.0,
        neighbor_resources={"forest": 3.0, "market": 8.0, "sea": 1.0},
    )

    action = agent.decide(obs)
    assert action.kind == "move"
    assert action.move_target == "market"


def test_rule_based_rests_when_no_better_neighbor_exists() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0)
    obs = _observation(
        energy=8.0,
        current_resource=0.0,
        neighbor_resources={"forest": 0.0, "market": 0.0, "sea": 0.0},
    )

    action = agent.decide(obs)
    assert action.kind == "rest"


def test_rule_based_follows_trusted_report_more_than_suspicious_report() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0)
    trusted_obs = _observation(
        energy=8.0,
        current_resource=6.0,
        neighbor_resources={"forest": 0.0, "market": 0.0},
        public_bulletins=(
            OpenWorldCommunication(
                t=0,
                sender_id=7,
                scope="public",
                location_id="forest",
                message="band:high",
                speech_act="inform",
                topic="resource_report",
            ),
        ),
        reputation_beliefs=(
            ReputationBelief(
                subject_id=7,
                honesty=0.85,
                reliability=0.8,
                confidence=0.7,
                label="trusted",
            ),
        ),
    )
    suspicious_obs = _observation(
        energy=8.0,
        current_resource=6.0,
        neighbor_resources={"forest": 0.0, "market": 0.0},
        public_bulletins=(
            OpenWorldCommunication(
                t=0,
                sender_id=9,
                scope="public",
                location_id="forest",
                message="band:high",
                speech_act="inform",
                topic="resource_report",
            ),
        ),
        reputation_beliefs=(
            ReputationBelief(
                subject_id=9,
                honesty=0.2,
                reliability=0.25,
                confidence=0.7,
                label="suspicious",
            ),
        ),
    )

    trusted_action = agent.decide(trusted_obs)
    suspicious_action = agent.decide(suspicious_obs)

    assert trusted_action.kind == "move"
    assert trusted_action.move_target == "forest"
    assert trusted_action.meta.get("communication_influenced") is True

    assert suspicious_action.kind == "gather"
    assert suspicious_action.meta == {}


def test_suspicious_broadcast_has_reduced_influence() -> None:
    agent = DeterministicOpenWorldAgent(agent_id=0, low_energy_threshold=3.0)
    obs = _observation(
        energy=8.0,
        current_resource=5.0,
        neighbor_resources={"forest": 0.0},
        public_bulletins=(
            OpenWorldCommunication(
                t=0,
                sender_id=4,
                scope="public",
                location_id="forest",
                message="band:high",
                speech_act="inform",
                topic="resource_report",
            ),
        ),
        reputation_beliefs=(
            ReputationBelief(
                subject_id=4,
                honesty=0.1,
                reliability=0.1,
                confidence=0.8,
                label="suspicious",
            ),
        ),
    )

    action = agent.decide(obs)
    assert action.kind == "gather"
