from __future__ import annotations

from typing import Any

from llm_social_simulation.simulation.open_world.types import OpenWorldEvent, OpenWorldTick

ZONE_ANCHORS: dict[str, tuple[float, float]] = {
    "forest": (4.0, 2.0),
    "sea": (12.0, 2.0),
    "farm": (4.0, 5.0),
    "market": (8.0, 5.0),
    "workshop": (12.0, 5.0),
    "town_hall": (8.0, 8.0),
    "clinic": (12.0, 8.0),
    "housing": (4.0, 8.0),
}

_AGENT_OFFSETS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (-0.5, 0.35),
    (0.5, 0.35),
    (-0.5, -0.35),
    (0.5, -0.35),
)


def _zone_anchor(zone_id: str) -> tuple[float, float]:
    if zone_id in ZONE_ANCHORS:
        return ZONE_ANCHORS[zone_id]
    return 8.0, 5.0


def _agent_position(zone_id: str, slot: int) -> tuple[float, float]:
    anchor_x, anchor_y = _zone_anchor(zone_id)
    dx, dy = _AGENT_OFFSETS[slot % len(_AGENT_OFFSETS)]
    return anchor_x + dx, anchor_y + dy


def _extract_gather_stats(event: OpenWorldEvent | None) -> tuple[float, float]:
    if event is None or event.kind != "gather":
        return 0.0, 0.0
    payload = dict(event.payload)
    requested = float(payload.get("requested", 0.0))
    actual = float(payload.get("actual", 0.0))
    return requested, actual


def _extract_communications(events: list[OpenWorldEvent]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for event in events:
        if event.kind not in {"talk_local", "broadcast"}:
            continue
        payload = dict(event.payload)
        raw_comm = payload.get("communication")
        comm = dict(raw_comm) if isinstance(raw_comm, dict) else {}
        scope = "local" if event.kind == "talk_local" else "public"
        entries.append(
            {
                "t": int(event.t),
                "agentId": int(event.agent_id),
                "scope": str(comm.get("scope", scope)),
                "locationId": str(comm.get("location_id", event.location_id)),
                "message": str(
                    comm.get(
                        "message",
                        event.action.message if event.action is not None else "",
                    )
                ),
                "speechAct": str(
                    comm.get(
                        "speech_act",
                        event.action.speech_act if event.action is not None else "inform",
                    )
                ),
                "topic": str(
                    comm.get(
                        "topic",
                        event.action.topic if event.action is not None else "resource",
                    )
                ),
            }
        )
    return entries


def to_open_world_replay_payload(
    *,
    run_id: str,
    ticks: list[OpenWorldTick],
    summary: dict[str, Any],
) -> dict[str, Any]:
    agent_type = str(summary.get("params", {}).get("agent_type", "rule"))
    default_label = "open-world-llm" if agent_type == "llm" else "deterministic-rule"
    agent_type_label = "open_world_llm" if agent_type == "llm" else "open_world_rule"
    model_labels = {
        str(agent_id): default_label
        for agent_id in sorted(int(key) for key in summary.get("final_agents", {}).keys())
    }

    replay_ticks: list[dict[str, Any]] = []
    for tick in ticks:
        locations_sorted = sorted(tick.locations.values(), key=lambda location: location.id)
        total_cap = float(sum(location.resource_cap for location in locations_sorted))
        total_resource = float(
            tick.metrics.get(
                "total_resource",
                sum(float(location.resource) for location in locations_sorted),
            )
        )
        total_credits = float(
            tick.metrics.get(
                "total_credits",
                sum(float(agent.wealth) for agent in tick.agents.values()),
            )
        )

        events = list(tick.events)
        communications = _extract_communications(events)
        governance = dict(tick.info.get("governance_summary", {}))
        latest_event_by_agent = {int(event.agent_id): event for event in events}
        zone_population: dict[str, int] = {}
        agents: list[dict[str, Any]] = []

        for agent_id in sorted(tick.agents.keys()):
            agent = tick.agents[agent_id]
            slot = zone_population.get(agent.location_id, 0)
            zone_population[agent.location_id] = slot + 1
            x, y = _agent_position(zone_id=agent.location_id, slot=slot)

            event = latest_event_by_agent.get(int(agent_id))
            requested, actual = _extract_gather_stats(event)
            reason = event.reason if event is not None else None
            clamped = {"harvest": bool(event is not None and not event.valid), "contribute": False}

            agents.append(
                {
                    "id": int(agent_id),
                    "type": agent_type_label,
                    "modelLabel": model_labels.get(str(agent_id), default_label),
                    "x": float(x),
                    "y": float(y),
                    "wealth": float(agent.wealth),
                    "action": {
                        "harvestRequested": float(requested),
                        "harvestActual": float(actual),
                        "contribute": 0.0,
                        "reward": 0.0,
                    },
                    "reason": reason,
                    "clamped": clamped,
                    "state": {
                        "locationId": str(agent.location_id),
                        "energy": float(agent.energy),
                        "inventory": dict(agent.inventory),
                    },
                }
            )

        zones = []
        for location in locations_sorted:
            zone_x, zone_y = _zone_anchor(location.id)
            zones.append(
                {
                    "id": location.id,
                    "x": float(zone_x),
                    "y": float(zone_y),
                    "resource": float(location.resource),
                    "resourceCap": float(location.resource_cap),
                    "regenRate": float(location.regen_rate),
                    "resourceType": str(location.meta.get("resource_type", "resource")),
                    "neighbors": list(location.neighbors),
                    "blocked": bool(location.blocked),
                }
            )

        replay_ticks.append(
            {
                "t": int(tick.t),
                "world": {
                    "resource": total_resource,
                    "resourceCap": total_cap,
                    "pool": total_credits,
                    "collapsed": bool(tick.metrics.get("collapsed", False)),
                },
                "agents": agents,
                "metrics": {
                    "totalHarvestRequested": float(
                        sum(a["action"]["harvestRequested"] for a in agents)
                    ),
                    "totalHarvestActual": float(sum(a["action"]["harvestActual"] for a in agents)),
                    "totalContribution": 0.0,
                    "totalReward": 0.0,
                    "moveTotal": int(tick.metrics.get("move_total", 0)),
                    "gatherTotal": int(tick.metrics.get("gather_total", 0)),
                    "restTotal": int(tick.metrics.get("rest_total", 0)),
                    "talkLocalTotal": int(tick.metrics.get("talk_local_total", 0)),
                    "broadcastTotal": int(tick.metrics.get("broadcast_total", 0)),
                    "proposeRuleTotal": int(tick.metrics.get("propose_rule_total", 0)),
                    "voteTotal": int(tick.metrics.get("vote_total", 0)),
                    "communicationTotal": int(tick.metrics.get("communication_total", 0)),
                    "invalidActionTotal": int(tick.metrics.get("invalid_action_total", 0)),
                    "avgEnergy": float(tick.metrics.get("avg_energy", 0.0)),
                    "totalCredits": total_credits,
                    "averageHonestyBelief": float(tick.metrics.get("average_honesty_belief", 0.0)),
                    "averageBeliefConfidence": float(
                        tick.metrics.get("average_belief_confidence", 0.0)
                    ),
                    "suspiciousLabelsCount": int(tick.metrics.get("suspicious_labels_count", 0)),
                    "validatedTruthfulReports": int(
                        tick.metrics.get("validated_truthful_reports", 0)
                    ),
                    "validatedFalseReports": int(tick.metrics.get("validated_false_reports", 0)),
                    "communicationInfluencedActionTotal": int(
                        tick.metrics.get("communication_influenced_action_total", 0)
                    ),
                    "trustedInfluenceActionTotal": int(
                        tick.metrics.get("trusted_influence_action_total", 0)
                    ),
                    "suspiciousDiscountActionTotal": int(
                        tick.metrics.get("suspicious_discount_action_total", 0)
                    ),
                    "governancePendingProposalsCount": int(
                        tick.metrics.get("governance_pending_proposals_count", 0)
                    ),
                    "governanceActiveRulesCount": int(
                        tick.metrics.get("governance_active_rules_count", 0)
                    ),
                    "governanceProposalCreatedTotal": int(
                        tick.metrics.get("governance_proposal_created_total", 0)
                    ),
                    "governanceVoteCastTotal": int(
                        tick.metrics.get("governance_vote_cast_total", 0)
                    ),
                    "governanceRuleActivatedTotal": int(
                        tick.metrics.get("governance_rule_activated_total", 0)
                    ),
                    "governanceRuleExpiredTotal": int(
                        tick.metrics.get("governance_rule_expired_total", 0)
                    ),
                },
                "zones": zones,
                "events": [event.to_dict() for event in events],
                "communications": communications,
                "reputation": dict(tick.info.get("reputation_summary", {})),
                "decisionInfluence": dict(tick.info.get("decision_influence_summary", {})),
                "governance": governance,
            }
        )

    return {
        "meta": {
            "runId": run_id,
            "scenario": "open-world-baseline",
            "modelLabels": model_labels,
            "mode": "open_world",
        },
        "ticks": replay_ticks,
    }
