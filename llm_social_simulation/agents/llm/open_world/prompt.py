from __future__ import annotations

import json
from collections.abc import Mapping

from llm_social_simulation.simulation.open_world.types import OpenWorldObservation


def _system_prompt() -> str:
    return (
        "You are an agent in a local-observation open-world simulation. "
        "Choose exactly one action for this tick: move, gather, rest, talk_local, broadcast, "
        "propose_rule, or vote. "
        "Use only the provided local observation (current zone + neighboring zones). "
        "Do not assume global map knowledge. "
        "Communication is not ground truth. Messages are claims/opinions only. "
        "Calibrate trust using visible reputation beliefs: trusted speakers are stronger signals, "
        "suspicious speakers should be discounted, unknown speakers have limited influence. "
        "For verifiable communication, prefer topic=resource_report or "
        "topic=risk_alert with explicit claims "
        "(e.g. 'band:low', 'risk:true'). "
        "Respond with JSON only (no markdown/code fences). "
        "Output schema: "
        '{"required":true,"self_id":<int>,"t":<int>,'
        '"action":{"kind":"move|gather|rest|talk_local|broadcast|propose_rule|vote",'
        '"move_target":<string|null>,"gather_resource":<string|null>,"amount":<float|null>,'
        '"message":<string|null>,"speech_act":<string|null>,"topic":<string|null>,'
        '"rule_template":<string|null>,"rule_params":<object|null>,'
        '"proposal_id":<string|null>,"vote_choice":"yes|no|null"},'
        '"reason":<string|null>}. '
        "Rules: move requires move_target, gather requires gather_resource and optional amount>0, "
        "talk_local/broadcast require message. "
        "propose_rule requires rule_template in {max_gather_per_tick,zone_restriction,"
        "broadcast_restriction_by_zone} and rule_params object. "
        "vote requires proposal_id and vote_choice yes/no. "
        "rest requires all optional fields null. "
        "Keep reason concise (<=20 words)."
    )


def _location_payload(location: Mapping[str, object]) -> dict[str, object]:
    meta = dict(location.get("meta", {})) if isinstance(location.get("meta"), Mapping) else {}
    return {
        "id": location.get("id"),
        "resource": float(location.get("resource", 0.0)),
        "resource_cap": float(location.get("resource_cap", 0.0)),
        "resource_type": str(meta.get("resource_type", "resource")),
        "resource_band": str(meta.get("resource_band", "unknown")),
    }


def _compact_reputation_summary(
    entries: list[dict[str, object]],
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    ranked = sorted(
        entries,
        key=lambda item: (
            -float(item.get("confidence", 0.0)),
            str(item.get("label", "")),
            int(item.get("subject_id", -1)),
        ),
    )
    return [
        {
            "subject_id": int(item.get("subject_id", -1)),
            "label": str(item.get("label", "unknown")),
            "honesty": round(float(item.get("honesty", 0.0)), 3),
            "reliability": round(float(item.get("reliability", 0.0)), 3),
            "confidence": round(float(item.get("confidence", 0.0)), 3),
        }
        for item in ranked[: int(limit)]
    ]


def build_open_world_messages(
    obs: OpenWorldObservation,
    *,
    run_id: str,
) -> tuple[Mapping[str, str], ...]:
    current_location = obs.location.to_dict()
    nearby_locations = [loc.to_dict() for loc in obs.nearby_locations]
    nearby_agents = [
        {
            "id": int(agent.id),
            "location_id": str(agent.location_id),
            "energy": float(agent.energy),
            "wealth": float(agent.wealth),
        }
        for agent in obs.nearby_agents
    ]
    recent_events = [
        {
            "t": int(event.t),
            "agent_id": int(event.agent_id),
            "kind": str(event.kind),
            "location_id": str(event.location_id),
            "valid": bool(event.valid),
        }
        for event in obs.recent_events[-8:]
    ]
    recent_communications = [communication.to_dict() for communication in obs.recent_communications]
    public_bulletins = [bulletin.to_dict() for bulletin in obs.public_bulletins]
    reputation_beliefs = [belief.to_dict() for belief in obs.reputation_beliefs]
    compact_reputation = _compact_reputation_summary(reputation_beliefs)
    pending_proposals = [proposal.to_dict() for proposal in obs.pending_proposals]
    active_rules = [rule.to_dict() for rule in obs.active_rules]

    resource_type = str(current_location.get("meta", {}).get("resource_type", "resource"))
    user_payload = {
        "run_id": run_id,
        "mode": "open_world",
        "decision_task": "Return exactly one action for this tick.",
        "observation": {
            "self_id": int(obs.self_id),
            "t": int(obs.t),
            "self_state": {
                "id": int(obs.self_state.id),
                "location_id": str(obs.self_state.location_id),
                "energy": float(obs.self_state.energy),
                "wealth": float(obs.self_state.wealth),
                "inventory": dict(obs.self_state.inventory),
            },
            "location": _location_payload(current_location),
            "nearby_locations": [_location_payload(loc) for loc in nearby_locations],
            "nearby_agents": nearby_agents,
            "recent_events": recent_events,
            "recent_communications": recent_communications,
            "public_bulletins": public_bulletins,
            "reputation_beliefs": compact_reputation,
            "reputation_beliefs_full_count": len(reputation_beliefs),
            "pending_proposals": pending_proposals,
            "active_rules": active_rules,
        },
        "constraints": {
            "allowed_actions": [
                "move",
                "gather",
                "rest",
                "talk_local",
                "broadcast",
                "propose_rule",
                "vote",
            ],
            "move_targets": list(obs.move_targets),
            "can_gather": bool(obs.action_space.get("can_gather", True)),
            "can_rest": bool(obs.action_space.get("can_rest", True)),
            "can_talk_local": bool(obs.action_space.get("can_talk_local", True)),
            "can_broadcast": bool(obs.action_space.get("can_broadcast", True)),
            "can_propose_rule": bool(obs.action_space.get("can_propose_rule", True)),
            "can_vote": bool(obs.action_space.get("can_vote", True)),
            "gather_resource_type": resource_type,
            "gather_amount_default": 1.0,
            "active_max_gather_per_tick": obs.action_space.get("active_max_gather_per_tick"),
            "max_message_length": int(obs.action_space.get("max_message_length", 160)),
            "speech_act_examples": ["inform", "warn", "request", "promise"],
            "topic_examples": [
                "resource",
                "resource_report",
                "risk_alert",
                "coordination",
                "status",
            ],
            "rule_templates": list(
                obs.action_space.get(
                    "rule_templates",
                    [
                        "max_gather_per_tick",
                        "zone_restriction",
                        "broadcast_restriction_by_zone",
                    ],
                )
            ),
            "votable_proposal_ids": list(obs.action_space.get("votable_proposal_ids", [])),
            "trust_calibration_hint": {
                "trusted_label": "higher_weight",
                "suspicious_label": "lower_weight",
                "unknown_label": "limited_weight",
            },
            "required_must_be_true": True,
        },
    }

    return (
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": json.dumps(user_payload, sort_keys=True, separators=(",", ":")),
        },
    )
