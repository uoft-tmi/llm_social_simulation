from __future__ import annotations

from llm_social_simulation.api.replay_adapters.open_world import to_open_world_replay_payload
from llm_social_simulation.simulation.open_world.types import OpenWorldAction
from llm_social_simulation.simulation.open_world.world import OpenWorldConfig, OpenWorldGameWorld


def _world() -> OpenWorldGameWorld:
    return OpenWorldGameWorld(OpenWorldConfig(agent_ids=(0, 1)))


def _proposal_id_from_tick(tick) -> str:
    proposal_event = next(event for event in tick.events if event.kind == "propose_rule")
    payload = dict(proposal_event.payload)
    proposal = dict(payload.get("proposal", {}))
    return str(proposal["proposal_id"])


def _activate_rule(world: OpenWorldGameWorld, proposal_action: OpenWorldAction) -> tuple[str, list]:
    ticks = []
    ticks.append(world.apply_actions({0: proposal_action, 1: OpenWorldAction(kind="rest")}))
    proposal_id = _proposal_id_from_tick(ticks[-1])

    # tick+1 enters voting; non-proposer votes.
    ticks.append(
        world.apply_actions(
            {
                0: OpenWorldAction(kind="rest"),
                1: OpenWorldAction(kind="vote", proposal_id=proposal_id, vote_choice="yes"),
            }
        )
    )

    # tick+2 resolves voting -> active.
    ticks.append(
        world.apply_actions({0: OpenWorldAction(kind="rest"), 1: OpenWorldAction(kind="rest")})
    )
    return proposal_id, ticks


def test_governance_proposals_can_be_created_and_seen_in_observation() -> None:
    world = _world()
    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="propose_rule",
                rule_template="max_gather_per_tick",
                rule_params={"max_amount": 0.5},
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )

    assert any(event.kind == "propose_rule" for event in tick.events)
    obs = world.get_observation(1)
    assert len(obs.pending_proposals) == 1
    assert obs.pending_proposals[0].status == "proposed"


def test_governance_votes_are_counted_and_rule_can_activate() -> None:
    world = _world()
    _, ticks = _activate_rule(
        world,
        OpenWorldAction(
            kind="propose_rule",
            rule_template="max_gather_per_tick",
            rule_params={"max_amount": 0.5},
        ),
    )

    vote_tick = ticks[1]
    assert any(event.kind == "vote" for event in vote_tick.events)
    activation_tick = ticks[2]
    assert any(event.kind == "rule_activated" for event in activation_tick.events)

    obs = world.get_observation(0)
    assert len(obs.active_rules) >= 1
    assert any(rule.template == "max_gather_per_tick" for rule in obs.active_rules)


def test_active_max_gather_rule_affects_validation() -> None:
    world = _world()
    _activate_rule(
        world,
        OpenWorldAction(
            kind="propose_rule",
            rule_template="max_gather_per_tick",
            rule_params={"max_amount": 0.5},
        ),
    )

    zone = world.locations[world.agents[0].location_id]
    resource_type = str(zone.meta.get("resource_type", "resource"))
    tick = world.apply_actions(
        {
            0: OpenWorldAction(kind="gather", gather_resource=resource_type, amount=2.0),
            1: OpenWorldAction(kind="rest"),
        }
    )

    invalid = [
        event for event in tick.events if event.kind == "invalid_action" and event.agent_id == 0
    ]
    assert invalid
    assert "max_gather" in str(invalid[0].reason)


def test_active_broadcast_zone_restriction_affects_validation() -> None:
    world = _world()
    restricted_zone = str(world.agents[0].location_id)
    _activate_rule(
        world,
        OpenWorldAction(
            kind="propose_rule",
            rule_template="broadcast_restriction_by_zone",
            rule_params={"zone_id": restricted_zone},
        ),
    )

    tick = world.apply_actions(
        {
            0: OpenWorldAction(
                kind="broadcast",
                message="go public",
                speech_act="inform",
                topic="status",
            ),
            1: OpenWorldAction(kind="rest"),
        }
    )

    invalid = [
        event for event in tick.events if event.kind == "invalid_action" and event.agent_id == 0
    ]
    assert invalid
    assert "broadcast" in str(invalid[0].reason)


def test_replay_includes_governance_summary_and_metrics() -> None:
    world = _world()
    _, ticks = _activate_rule(
        world,
        OpenWorldAction(
            kind="propose_rule",
            rule_template="zone_restriction",
            rule_params={"zone_id": "forest"},
        ),
    )

    replay = to_open_world_replay_payload(
        run_id="run_governance_test",
        ticks=ticks,
        summary={
            "params": {"agent_type": "rule"},
            "final_agents": {
                str(agent_id): {"credits": float(agent.wealth)}
                for agent_id, agent in world.agents.items()
            },
        },
    )

    replay_tick = replay["ticks"][-1]
    assert "governance" in replay_tick
    assert "active_rules" in replay_tick["governance"]
    assert "governanceActiveRulesCount" in replay_tick["metrics"]
    assert "governanceVoteCastTotal" in replay_tick["metrics"]
