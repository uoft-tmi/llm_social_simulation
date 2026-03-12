from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .types import (
    AgentState,
    GovernanceProposal,
    GovernanceRule,
    LocationState,
    OpenWorldAction,
    OpenWorldCommunication,
    OpenWorldEvent,
    OpenWorldObservation,
    OpenWorldTick,
    ReputationBelief,
)

ZONE_ORDER = (
    "forest",
    "sea",
    "farm",
    "market",
    "workshop",
    "town_hall",
    "clinic",
    "housing",
)

ZONE_GRAPH: dict[str, tuple[str, ...]] = {
    "forest": ("farm", "workshop", "housing"),
    "sea": ("market", "clinic"),
    "farm": ("forest", "market", "housing"),
    "market": ("sea", "farm", "workshop", "town_hall"),
    "workshop": ("forest", "market", "town_hall", "housing"),
    "town_hall": ("market", "workshop", "clinic", "housing"),
    "clinic": ("sea", "town_hall", "housing"),
    "housing": ("forest", "farm", "workshop", "town_hall", "clinic"),
}

ZONE_RESOURCE_SPEC: dict[str, dict[str, float | str]] = {
    "forest": {"resource_type": "wood", "resource_cap": 20.0, "regen_rate": 1.6},
    "sea": {"resource_type": "fish", "resource_cap": 18.0, "regen_rate": 1.4},
    "farm": {"resource_type": "grain", "resource_cap": 16.0, "regen_rate": 1.2},
    "market": {"resource_type": "goods", "resource_cap": 10.0, "regen_rate": 0.6},
    "workshop": {"resource_type": "tools", "resource_cap": 12.0, "regen_rate": 0.8},
    "town_hall": {"resource_type": "permits", "resource_cap": 8.0, "regen_rate": 0.5},
    "clinic": {"resource_type": "medicine", "resource_cap": 10.0, "regen_rate": 0.7},
    "housing": {"resource_type": "labor", "resource_cap": 14.0, "regen_rate": 0.9},
}

RESOURCE_CREDIT_VALUES: dict[str, float] = {
    "wood": 1.0,
    "fish": 1.2,
    "grain": 1.1,
    "goods": 1.5,
    "tools": 1.8,
    "permits": 0.9,
    "medicine": 2.0,
    "labor": 0.8,
}

GOVERNANCE_RULE_TEMPLATES: tuple[str, ...] = (
    "max_gather_per_tick",
    "zone_restriction",
    "broadcast_restriction_by_zone",
)


@dataclass(frozen=True)
class OpenWorldConfig:
    agent_ids: tuple[int, ...]
    initial_energy: float = 8.0
    max_energy: float = 10.0
    rest_recovery: float = 2.0
    move_energy_cost: float = 0.5
    gather_energy_cost: float = 1.0
    default_gather_amount: float = 1.0
    initial_resource_frac: float = 0.7
    max_recent_events_in_observation: int = 12
    max_recent_communications_in_observation: int = 12
    max_public_bulletins_in_observation: int = 12
    communication_history_limit: int = 400
    max_message_length: int = 160
    broadcast_allowed_zones: tuple[str, ...] | None = None
    governance_vote_window_ticks: int = 1
    governance_rule_duration_ticks: int = 4
    governance_history_limit: int = 120


class OpenWorldGameWorld:
    """
    Minimal deterministic open-world game state and transition rules.

    Engine contract:
    - get_observation(agent_id) -> OpenWorldObservation
    - apply_actions(actions_by_agent) -> OpenWorldTick
    """

    def __init__(self, config: OpenWorldConfig):
        self.config = config
        self._validate_zone_graph()
        self.t = 0
        self.locations = self._build_locations(
            initial_resource_frac=float(config.initial_resource_frac)
        )
        self.agents = self._build_agents()
        self._reputation_beliefs = self._build_initial_reputation_beliefs()
        self._recent_events: list[OpenWorldEvent] = []
        self._communications: list[OpenWorldCommunication] = []
        self._proposal_seq = 0
        self._active_rule_seq = 0
        self._proposals: dict[str, GovernanceProposal] = {}
        self._active_rules: dict[str, GovernanceRule] = {}

    def _validate_zone_graph(self) -> None:
        if set(ZONE_GRAPH.keys()) != set(ZONE_ORDER):
            raise ValueError("ZONE_GRAPH keys must exactly match ZONE_ORDER")
        for zone, neighbors in ZONE_GRAPH.items():
            for neighbor in neighbors:
                if zone not in ZONE_GRAPH.get(neighbor, ()):
                    raise ValueError(f"Adjacency is not symmetric: {zone} -> {neighbor}")

    def _build_locations(self, *, initial_resource_frac: float) -> dict[str, LocationState]:
        frac = min(1.0, max(0.0, float(initial_resource_frac)))
        out: dict[str, LocationState] = {}
        for zone in ZONE_ORDER:
            spec = ZONE_RESOURCE_SPEC[zone]
            cap = float(spec["resource_cap"])
            out[zone] = LocationState(
                id=zone,
                resource=cap * frac,
                resource_cap=cap,
                regen_rate=float(spec["regen_rate"]),
                neighbors=tuple(ZONE_GRAPH[zone]),
                blocked=False,
                meta={"resource_type": str(spec["resource_type"]), "zone_role": zone},
            )
        return out

    def _build_agents(self) -> dict[int, AgentState]:
        spawn_cycle = (
            "housing",
            "farm",
            "market",
            "workshop",
            "forest",
            "sea",
            "town_hall",
            "clinic",
        )
        out: dict[int, AgentState] = {}
        for idx, agent_id in enumerate(sorted(self.config.agent_ids)):
            location_id = spawn_cycle[idx % len(spawn_cycle)]
            out[int(agent_id)] = AgentState(
                id=int(agent_id),
                location_id=location_id,
                inventory={},
                energy=float(self.config.initial_energy),
                wealth=0.0,
                persona_tag="rule_based",
                memory_summary=None,
                last_action=None,
                meta={"credits": 0.0},
            )
        return out

    def _build_initial_reputation_beliefs(self) -> dict[int, dict[int, ReputationBelief]]:
        beliefs: dict[int, dict[int, ReputationBelief]] = {}
        for observer_id in sorted(self.config.agent_ids):
            observer_beliefs: dict[int, ReputationBelief] = {}
            for subject_id in sorted(self.config.agent_ids):
                if int(subject_id) == int(observer_id):
                    continue
                observer_beliefs[int(subject_id)] = ReputationBelief(subject_id=int(subject_id))
            beliefs[int(observer_id)] = observer_beliefs
        return beliefs

    @staticmethod
    def _resource_band(resource: float, cap: float) -> str:
        if cap <= 0.0:
            return "empty"
        frac = max(0.0, min(1.0, resource / cap))
        if frac <= 0.0:
            return "empty"
        if frac < 0.34:
            return "low"
        if frac < 0.67:
            return "medium"
        return "high"

    def _coarse_location_state(self, location: LocationState) -> LocationState:
        coarse_meta = dict(location.meta)
        coarse_meta["coarse"] = True
        coarse_meta["resource_band"] = self._resource_band(location.resource, location.resource_cap)
        return replace(location, neighbors=(), meta=coarse_meta)

    def _is_broadcast_allowed(self, location_id: str) -> bool:
        allowed = self.config.broadcast_allowed_zones
        baseline_allowed = True
        if allowed is not None:
            baseline_allowed = str(location_id) in set(str(item) for item in allowed)
        if not baseline_allowed:
            return False

        restricted_zones = self._active_broadcast_restricted_zones()
        return str(location_id) not in restricted_zones

    def _active_max_gather_per_tick(self) -> float | None:
        active_limits: list[float] = []
        for rule in self._active_rules.values():
            if rule.template != "max_gather_per_tick":
                continue
            value = rule.params.get("max_amount")
            try:
                amount = float(value)
            except (TypeError, ValueError):
                continue
            if amount > 0.0:
                active_limits.append(amount)
        if not active_limits:
            return None
        return min(active_limits)

    def _active_zone_restrictions(self) -> set[str]:
        restricted: set[str] = set()
        for rule in self._active_rules.values():
            if rule.template != "zone_restriction":
                continue
            zone_id = str(rule.params.get("zone_id", "")).strip()
            if zone_id:
                restricted.add(zone_id)
        return restricted

    def _active_broadcast_restricted_zones(self) -> set[str]:
        restricted: set[str] = set()
        for rule in self._active_rules.values():
            if rule.template != "broadcast_restriction_by_zone":
                continue
            zone_id = str(rule.params.get("zone_id", "")).strip()
            if zone_id:
                restricted.add(zone_id)
        return restricted

    def _next_proposal_id(self) -> str:
        self._proposal_seq += 1
        return f"proposal_{self._proposal_seq:04d}"

    def _next_rule_id(self) -> str:
        self._active_rule_seq += 1
        return f"rule_{self._active_rule_seq:04d}"

    def _normalize_rule_template_and_params(
        self,
        *,
        template: str,
        params: Mapping[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        tmpl = str(template).strip().lower()
        if tmpl not in set(GOVERNANCE_RULE_TEMPLATES):
            raise ValueError(f"unsupported_rule_template:{tmpl}")
        raw = {} if params is None else dict(params)

        if tmpl == "max_gather_per_tick":
            default = float(self.config.default_gather_amount)
            max_amount = float(raw.get("max_amount", default))
            if max_amount <= 0.0:
                raise ValueError("max_amount_must_be_positive")
            max_amount = round(max_amount, 4)
            return tmpl, {"max_amount": max_amount}

        zone_id = str(raw.get("zone_id", "")).strip()
        if zone_id not in self.locations:
            raise ValueError("invalid_zone_id")
        return tmpl, {"zone_id": zone_id}

    def _sorted_pending_proposals(self) -> tuple[GovernanceProposal, ...]:
        pending = [
            proposal
            for proposal in self._proposals.values()
            if proposal.status in {"proposed", "voting"}
        ]
        pending.sort(key=lambda item: (int(item.created_t), str(item.proposal_id)))
        return tuple(pending)

    def _sorted_active_rules(self) -> tuple[GovernanceRule, ...]:
        active = list(self._active_rules.values())
        active.sort(key=lambda item: (int(item.activated_t), str(item.rule_id)))
        return tuple(active)

    def _advance_governance_state(self, *, t_now: int) -> list[OpenWorldEvent]:
        lifecycle_events: list[OpenWorldEvent] = []
        vote_window = max(1, int(self.config.governance_vote_window_ticks))
        default_duration = max(1, int(self.config.governance_rule_duration_ticks))

        # 1) proposals -> voting
        for proposal in list(self._proposals.values()):
            if proposal.status != "proposed":
                continue
            if t_now <= int(proposal.created_t):
                continue
            voting_end_t = t_now + vote_window
            self._proposals[proposal.proposal_id] = replace(
                proposal,
                status="voting",
                voting_start_t=t_now,
                voting_end_t=voting_end_t,
                meta={**dict(proposal.meta), "last_transition_t": t_now},
            )

        # 2) voting -> active/expired
        for proposal in list(self._proposals.values()):
            if proposal.status != "voting":
                continue
            voting_end_t = t_now if proposal.voting_end_t is None else int(proposal.voting_end_t)
            if t_now < voting_end_t:
                continue

            yes_votes = sum(1 for vote in proposal.votes.values() if vote == "yes")
            no_votes = sum(1 for vote in proposal.votes.values() if vote == "no")
            approved = yes_votes > no_votes

            if approved:
                rule_id = self._next_rule_id()
                ttl = int(proposal.params.get("duration_ticks", default_duration))
                ttl = max(1, ttl)
                rule = GovernanceRule(
                    rule_id=rule_id,
                    template=proposal.template,
                    params=dict(proposal.params),
                    source_proposal_id=proposal.proposal_id,
                    activated_t=t_now,
                    expires_t=t_now + ttl,
                    meta={"yes_votes": yes_votes, "no_votes": no_votes},
                )
                self._active_rules[rule_id] = rule
                updated = replace(
                    proposal,
                    status="active",
                    activation_t=t_now,
                    expiry_t=rule.expires_t,
                    meta={
                        **dict(proposal.meta),
                        "approved": True,
                        "yes_votes": yes_votes,
                        "no_votes": no_votes,
                        "active_rule_id": rule_id,
                    },
                )
                self._proposals[proposal.proposal_id] = updated
                lifecycle_events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=int(proposal.proposer_id),
                        kind="rule_activated",
                        location_id=str(self.agents[int(proposal.proposer_id)].location_id),
                        action=None,
                        valid=True,
                        reason="governance_rule_activated",
                        payload={
                            "proposal": updated.to_dict(),
                            "rule": rule.to_dict(),
                            "yes_votes": yes_votes,
                            "no_votes": no_votes,
                        },
                    )
                )
            else:
                updated = replace(
                    proposal,
                    status="expired",
                    activation_t=None,
                    expiry_t=t_now,
                    meta={
                        **dict(proposal.meta),
                        "approved": False,
                        "yes_votes": yes_votes,
                        "no_votes": no_votes,
                    },
                )
                self._proposals[proposal.proposal_id] = updated

        # 3) active rules -> expired
        for rule_id, rule in list(self._active_rules.items()):
            if t_now < int(rule.expires_t):
                continue
            self._active_rules.pop(rule_id, None)
            lifecycle_events.append(
                OpenWorldEvent(
                    t=t_now,
                    agent_id=-1,
                    kind="rule_expired",
                    location_id="town_hall",
                    action=None,
                    valid=True,
                    reason="governance_rule_expired",
                    payload={"rule": rule.to_dict()},
                )
            )
            proposal = self._proposals.get(rule.source_proposal_id)
            if proposal is not None and proposal.status != "expired":
                self._proposals[proposal.proposal_id] = replace(
                    proposal,
                    status="expired",
                    expiry_t=t_now,
                    meta={**dict(proposal.meta), "expired_t": t_now},
                )

        # bound proposal history to avoid unbounded memory
        history_limit = max(20, int(self.config.governance_history_limit))
        if len(self._proposals) > history_limit:
            ordered_ids = sorted(
                self._proposals.keys(),
                key=lambda proposal_id: (
                    int(self._proposals[proposal_id].created_t),
                    str(proposal_id),
                ),
            )
            overflow = len(self._proposals) - history_limit
            for proposal_id in ordered_ids[:overflow]:
                proposal = self._proposals[proposal_id]
                if proposal.status in {"proposed", "voting"}:
                    continue
                self._proposals.pop(proposal_id, None)

        return lifecycle_events

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _derive_reputation_label(*, honesty: float, reliability: float, confidence: float) -> str:
        if confidence < 0.20:
            return "unknown"
        if honesty <= 0.35 or reliability <= 0.30:
            return "suspicious"
        if honesty >= 0.65 and reliability >= 0.65:
            return "trusted"
        return "neutral"

    def _upsert_reputation_belief(self, *, observer_id: int, subject_id: int) -> ReputationBelief:
        if observer_id == subject_id:
            raise ValueError("observer_id and subject_id must differ")
        observer_beliefs = self._reputation_beliefs.setdefault(int(observer_id), {})
        current = observer_beliefs.get(int(subject_id))
        if current is not None:
            return current
        current = ReputationBelief(subject_id=int(subject_id))
        observer_beliefs[int(subject_id)] = current
        return current

    def _apply_reputation_update(
        self,
        *,
        observer_id: int,
        subject_id: int,
        honesty_delta: float = 0.0,
        reliability_delta: float = 0.0,
        confidence_delta: float = 0.0,
        truthful_report_delta: int = 0,
        false_report_delta: int = 0,
        evidence_note: str | None = None,
    ) -> ReputationBelief:
        current = self._upsert_reputation_belief(observer_id=observer_id, subject_id=subject_id)
        honesty = self._clamp_score(float(current.honesty) + float(honesty_delta))
        reliability = self._clamp_score(float(current.reliability) + float(reliability_delta))
        confidence = self._clamp_score(float(current.confidence) + float(confidence_delta))
        truthful_reports = int(current.truthful_reports) + int(max(0, truthful_report_delta))
        false_reports = int(current.false_reports) + int(max(0, false_report_delta))
        evidence_count = int(current.evidence_count) + 1
        label = self._derive_reputation_label(
            honesty=honesty,
            reliability=reliability,
            confidence=confidence,
        )
        meta = dict(current.meta)
        if evidence_note:
            meta["last_evidence"] = str(evidence_note)

        updated = ReputationBelief(
            subject_id=int(subject_id),
            honesty=honesty,
            reliability=reliability,
            confidence=confidence,
            label=label,  # type: ignore[arg-type]
            evidence_count=evidence_count,
            truthful_reports=truthful_reports,
            false_reports=false_reports,
            meta=meta,
        )
        self._reputation_beliefs[int(observer_id)][int(subject_id)] = updated
        return updated

    @staticmethod
    def _parse_resource_band_claim(message: str) -> str | None:
        text = str(message).strip().lower()
        if not text:
            return None
        explicit = re.search(r"\bband\s*[:=]\s*(empty|low|medium|high)\b", text)
        if explicit:
            return str(explicit.group(1))
        loose = re.search(r"\b(empty|low|medium|high)\b", text)
        if loose:
            return str(loose.group(1))
        return None

    @staticmethod
    def _parse_risk_claim(message: str) -> bool | None:
        text = str(message).strip().lower()
        if not text:
            return None
        explicit = re.search(r"\brisk\s*[:=]\s*(true|false|1|0|high|low)\b", text)
        if explicit:
            token = str(explicit.group(1))
            if token in {"true", "1", "high"}:
                return True
            if token in {"false", "0", "low"}:
                return False
        if "no risk" in text or "safe" in text or "stable" in text:
            return False
        if any(token in text for token in ("risk", "danger", "unsafe", "alert", "threat")):
            return True
        return None

    def _evaluate_communication_evidence(
        self,
        *,
        communication: OpenWorldCommunication,
        locations_snapshot: Mapping[str, LocationState],
    ) -> dict[str, Any] | None:
        topic = str(communication.topic)
        location = locations_snapshot.get(str(communication.location_id))
        if location is None:
            return None

        if topic == "resource_report":
            claim_band = self._parse_resource_band_claim(communication.message)
            actual_band = self._resource_band(
                float(location.resource),
                float(location.resource_cap),
            )
            verifiable = claim_band is not None
            truthful = (claim_band == actual_band) if verifiable else None
            return {
                "evidence_type": "resource_report",
                "verifiable": bool(verifiable),
                "truthful": truthful,
                "claim": claim_band,
                "actual": actual_band,
            }

        if topic == "risk_alert":
            claim_risk = self._parse_risk_claim(communication.message)
            current_band = self._resource_band(
                float(location.resource),
                float(location.resource_cap),
            )
            neighbor_bands = [
                self._resource_band(
                    float(locations_snapshot[neighbor_id].resource),
                    float(locations_snapshot[neighbor_id].resource_cap),
                )
                for neighbor_id in location.neighbors
                if neighbor_id in locations_snapshot
            ]
            actual_risk = bool(
                current_band in {"empty", "low"}
                or any(band in {"empty", "low"} for band in neighbor_bands)
            )
            verifiable = claim_risk is not None
            truthful = (bool(claim_risk) == actual_risk) if verifiable else None
            return {
                "evidence_type": "risk_alert",
                "verifiable": bool(verifiable),
                "truthful": truthful,
                "claim": claim_risk,
                "actual": actual_risk,
            }

        return None

    @staticmethod
    def _communication_visible_to_observer(
        *,
        communication: OpenWorldCommunication,
        observer_state: AgentState,
    ) -> bool:
        if communication.scope == "public":
            return True
        return str(communication.location_id) == str(observer_state.location_id)

    def _visible_location_ids_for_agent(
        self,
        *,
        agent_state: AgentState,
        locations_snapshot: Mapping[str, LocationState],
    ) -> set[str]:
        location = locations_snapshot[str(agent_state.location_id)]
        return {location.id, *location.neighbors}

    def _visible_reputation_beliefs_for_observer(
        self,
        *,
        observer_id: int,
        nearby_agents: list[AgentState],
        local_communications: list[OpenWorldCommunication],
        public_bulletins: list[OpenWorldCommunication],
    ) -> tuple[ReputationBelief, ...]:
        observer_beliefs = self._reputation_beliefs.get(int(observer_id), {})
        visible_subject_ids = {int(agent.id) for agent in nearby_agents}
        visible_subject_ids.update(int(comm.sender_id) for comm in local_communications)
        visible_subject_ids.update(int(comm.sender_id) for comm in public_bulletins)
        visible_subject_ids.discard(int(observer_id))

        beliefs: list[ReputationBelief] = []
        for subject_id in sorted(visible_subject_ids):
            beliefs.append(
                observer_beliefs.get(int(subject_id), ReputationBelief(subject_id=int(subject_id)))
            )
        return tuple(beliefs)

    def _update_reputation_beliefs(
        self,
        *,
        events: list[OpenWorldEvent],
        communications: list[OpenWorldCommunication],
        agents_snapshot: Mapping[int, AgentState],
        locations_snapshot: Mapping[str, LocationState],
    ) -> dict[str, Any]:
        validated_truthful_reports = 0
        validated_false_reports = 0
        for communication in communications:
            evidence = communication.meta.get("reputation_evidence")
            if not isinstance(evidence, Mapping) or not bool(evidence.get("verifiable", False)):
                continue
            truthful = evidence.get("truthful")
            if truthful is True:
                validated_truthful_reports += 1
            elif truthful is False:
                validated_false_reports += 1

        for observer_id in sorted(agents_snapshot.keys()):
            observer_state = agents_snapshot[observer_id]
            visible_location_ids = self._visible_location_ids_for_agent(
                agent_state=observer_state,
                locations_snapshot=locations_snapshot,
            )

            for event in events:
                subject_id = int(event.agent_id)
                if subject_id == int(observer_id):
                    continue
                if str(event.location_id) not in visible_location_ids:
                    continue
                if event.kind == "invalid_action":
                    self._apply_reputation_update(
                        observer_id=observer_id,
                        subject_id=subject_id,
                        reliability_delta=-0.12,
                        confidence_delta=0.08,
                        evidence_note="visible_invalid_action",
                    )
                else:
                    self._apply_reputation_update(
                        observer_id=observer_id,
                        subject_id=subject_id,
                        reliability_delta=0.03,
                        confidence_delta=0.04,
                        evidence_note=f"visible_action:{event.kind}",
                    )

            for communication in communications:
                subject_id = int(communication.sender_id)
                if subject_id == int(observer_id):
                    continue
                if not self._communication_visible_to_observer(
                    communication=communication,
                    observer_state=observer_state,
                ):
                    continue

                evidence = communication.meta.get("reputation_evidence")
                if not isinstance(evidence, Mapping) or not bool(evidence.get("verifiable", False)):
                    continue
                truthful = evidence.get("truthful")
                if truthful is True:
                    self._apply_reputation_update(
                        observer_id=observer_id,
                        subject_id=subject_id,
                        honesty_delta=0.12,
                        reliability_delta=0.05,
                        confidence_delta=0.10,
                        truthful_report_delta=1,
                        evidence_note=str(evidence.get("evidence_type", "verified_true")),
                    )
                elif truthful is False:
                    self._apply_reputation_update(
                        observer_id=observer_id,
                        subject_id=subject_id,
                        honesty_delta=-0.18,
                        reliability_delta=-0.08,
                        confidence_delta=0.12,
                        false_report_delta=1,
                        evidence_note=str(evidence.get("evidence_type", "verified_false")),
                    )

        all_beliefs = [
            belief
            for observer_beliefs in self._reputation_beliefs.values()
            for belief in observer_beliefs.values()
        ]
        avg_honesty = sum(float(item.honesty) for item in all_beliefs) / max(1, len(all_beliefs))
        avg_confidence = sum(float(item.confidence) for item in all_beliefs) / max(
            1, len(all_beliefs)
        )
        suspicious_count = sum(1 for item in all_beliefs if item.label == "suspicious")

        by_observer: dict[str, list[dict[str, Any]]] = {}
        for observer_id, observer_beliefs in sorted(self._reputation_beliefs.items()):
            ranked = sorted(
                observer_beliefs.values(),
                key=lambda item: (-float(item.confidence), int(item.subject_id)),
            )[:6]
            by_observer[str(observer_id)] = [
                {
                    "subject_id": int(item.subject_id),
                    "honesty": round(float(item.honesty), 4),
                    "reliability": round(float(item.reliability), 4),
                    "confidence": round(float(item.confidence), 4),
                    "label": str(item.label),
                }
                for item in ranked
            ]

        return {
            "average_honesty_belief": float(avg_honesty),
            "average_belief_confidence": float(avg_confidence),
            "suspicious_labels_count": int(suspicious_count),
            "validated_truthful_reports": int(validated_truthful_reports),
            "validated_false_reports": int(validated_false_reports),
            "by_observer": by_observer,
        }

    def get_observation(self, agent_id: int) -> OpenWorldObservation:
        if agent_id not in self.agents:
            raise ValueError(f"Unknown agent_id: {agent_id}")

        self_state = self.agents[agent_id]
        current_location = self.locations[self_state.location_id]
        neighbor_ids = tuple(current_location.neighbors)
        nearby_locations = tuple(
            self._coarse_location_state(self.locations[neighbor_id]) for neighbor_id in neighbor_ids
        )

        visible_location_ids = {current_location.id, *neighbor_ids}
        nearby_agents: list[AgentState] = []
        for other_id in sorted(self.agents.keys()):
            if other_id == agent_id:
                continue
            other = self.agents[other_id]
            if other.location_id in visible_location_ids:
                nearby_agents.append(other)

        local_events = [
            event for event in self._recent_events if event.location_id in visible_location_ids
        ]
        if len(local_events) > int(self.config.max_recent_events_in_observation):
            local_events = local_events[-int(self.config.max_recent_events_in_observation) :]

        local_communications = [
            communication
            for communication in self._communications
            if communication.scope == "local" and communication.location_id == current_location.id
        ]
        if len(local_communications) > int(self.config.max_recent_communications_in_observation):
            local_communications = local_communications[
                -int(self.config.max_recent_communications_in_observation) :
            ]

        public_bulletins = [
            communication
            for communication in self._communications
            if communication.scope == "public"
        ]
        if len(public_bulletins) > int(self.config.max_public_bulletins_in_observation):
            public_bulletins = public_bulletins[
                -int(self.config.max_public_bulletins_in_observation) :
            ]

        reputation_beliefs = self._visible_reputation_beliefs_for_observer(
            observer_id=agent_id,
            nearby_agents=nearby_agents,
            local_communications=local_communications,
            public_bulletins=public_bulletins,
        )
        pending_proposals = self._sorted_pending_proposals()
        active_rules = self._sorted_active_rules()
        active_zone_restrictions = self._active_zone_restrictions()
        votable_proposal_ids = [
            str(proposal.proposal_id)
            for proposal in pending_proposals
            if proposal.status == "voting"
        ]
        move_targets = [
            neighbor_id
            for neighbor_id in neighbor_ids
            if neighbor_id not in active_zone_restrictions
        ]

        action_space = {
            "move_targets": move_targets,
            "can_gather": bool(
                current_location.resource > 0.0
                and not current_location.blocked
                and current_location.id not in active_zone_restrictions
            ),
            "can_rest": True,
            "can_talk_local": True,
            "can_broadcast": bool(self._is_broadcast_allowed(current_location.id)),
            "can_propose_rule": True,
            "can_vote": bool(votable_proposal_ids),
            "max_message_length": int(self.config.max_message_length),
            "rule_templates": list(GOVERNANCE_RULE_TEMPLATES),
            "votable_proposal_ids": votable_proposal_ids,
        }
        active_max_gather = self._active_max_gather_per_tick()
        if active_max_gather is not None:
            action_space["active_max_gather_per_tick"] = float(active_max_gather)
        action_space["active_zone_restrictions"] = sorted(self._active_zone_restrictions())
        action_space["active_broadcast_restrictions"] = sorted(
            self._active_broadcast_restricted_zones()
        )

        return OpenWorldObservation(
            self_id=agent_id,
            t=self.t,
            self_state=self_state,
            location=current_location,
            nearby_locations=nearby_locations,
            nearby_agents=tuple(nearby_agents),
            recent_events=tuple(local_events),
            recent_communications=tuple(local_communications),
            public_bulletins=tuple(public_bulletins),
            reputation_beliefs=reputation_beliefs,
            pending_proposals=pending_proposals,
            active_rules=active_rules,
            action_space=action_space,
            info={
                "mode": "open_world",
                "observation_scope": "local",
                "current_zone_resource_type": current_location.meta.get("resource_type"),
                "local_communication_count": len(local_communications),
                "public_bulletin_count": len(public_bulletins),
                "visible_reputation_belief_count": len(reputation_beliefs),
                "pending_proposals_count": len(pending_proposals),
                "active_rules_count": len(active_rules),
            },
        )

    def _coerce_action(self, raw_action: OpenWorldAction | Mapping[str, Any]) -> OpenWorldAction:
        if isinstance(raw_action, OpenWorldAction):
            return raw_action
        if isinstance(raw_action, Mapping):
            return OpenWorldAction.from_dict(raw_action)
        raise ValueError(f"Unsupported action payload type: {type(raw_action).__name__}")

    def _validate_action_against_world(
        self,
        *,
        agent: AgentState,
        obs: OpenWorldObservation,
        action: OpenWorldAction,
        locations_snapshot: Mapping[str, LocationState],
    ) -> None:
        obs.validate_action(action)
        active_zone_restrictions = self._active_zone_restrictions()
        active_max_gather = self._active_max_gather_per_tick()

        if action.kind == "move" and agent.energy < float(self.config.move_energy_cost):
            raise ValueError("insufficient_energy_for_move")
        if action.kind == "move" and str(action.move_target) in active_zone_restrictions:
            raise ValueError("zone_restriction_active_for_move")

        if action.kind == "gather":
            if str(agent.location_id) in active_zone_restrictions:
                raise ValueError("zone_restriction_active_for_gather")
            if agent.energy < float(self.config.gather_energy_cost):
                raise ValueError("insufficient_energy_for_gather")
            loc = locations_snapshot[agent.location_id]
            expected_type = str(loc.meta.get("resource_type", "resource"))
            if action.gather_resource != expected_type:
                raise ValueError(
                    "invalid_resource_type_for_zone: "
                    f"expected {expected_type}, got {action.gather_resource}"
                )
            requested = (
                float(self.config.default_gather_amount)
                if action.amount is None
                else float(action.amount)
            )
            if active_max_gather is not None and requested > float(active_max_gather):
                raise ValueError("gather_amount_exceeds_active_max_gather_rule")
            if loc.resource <= 0.0:
                raise ValueError("resource_depleted")
            return

        if action.kind in {"talk_local", "broadcast"}:
            message = str(action.message or "").strip()
            if not message:
                raise ValueError("empty_message")
            if len(message) > int(self.config.max_message_length):
                raise ValueError("message_too_long")
            if action.kind == "broadcast" and not self._is_broadcast_allowed(agent.location_id):
                raise ValueError("broadcast_not_allowed_in_zone")
            return

        if action.kind == "propose_rule":
            self._normalize_rule_template_and_params(
                template=str(action.rule_template or ""),
                params=action.rule_params,
            )
            return

        if action.kind == "vote":
            proposal = self._proposals.get(str(action.proposal_id))
            if proposal is None:
                raise ValueError("unknown_proposal_id")
            if proposal.status != "voting":
                raise ValueError("proposal_not_in_voting_state")
            if int(agent.id) == int(proposal.proposer_id):
                raise ValueError("proposer_cannot_vote_on_own_proposal")

    def _credit_value(self, resource_type: str) -> float:
        return float(RESOURCE_CREDIT_VALUES.get(str(resource_type), 1.0))

    def apply_actions(
        self,
        actions: Mapping[int, OpenWorldAction | Mapping[str, Any]],
    ) -> OpenWorldTick:
        t_now = self.t
        governance_events = self._advance_governance_state(t_now=t_now)
        agent_ids = tuple(sorted(self.config.agent_ids))

        locations_before = dict(self.locations)
        agents_before = dict(self.agents)
        observations = {agent_id: self.get_observation(agent_id) for agent_id in agent_ids}

        resolved_actions: dict[int, OpenWorldAction] = {}
        invalid_agents: set[int] = set()
        events: list[OpenWorldEvent] = list(governance_events)

        for agent_id in agent_ids:
            agent = agents_before[agent_id]
            raw_action = actions.get(agent_id)
            if raw_action is None:
                invalid_agents.add(agent_id)
                resolved_actions[agent_id] = OpenWorldAction(kind="rest")
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="invalid_action",
                        location_id=agent.location_id,
                        action=None,
                        valid=False,
                        reason="missing_action",
                        payload={"resolution": "no_op"},
                    )
                )
                continue

            parsed_action: OpenWorldAction | None = None
            try:
                parsed_action = self._coerce_action(raw_action)
                self._validate_action_against_world(
                    agent=agent,
                    obs=observations[agent_id],
                    action=parsed_action,
                    locations_snapshot=locations_before,
                )
                resolved_actions[agent_id] = parsed_action
            except Exception as exc:
                invalid_agents.add(agent_id)
                resolved_actions[agent_id] = OpenWorldAction(kind="rest")
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="invalid_action",
                        location_id=agent.location_id,
                        action=parsed_action,
                        valid=False,
                        reason=f"{type(exc).__name__}: {exc}",
                        payload={"resolution": "no_op"},
                    )
                )

        locations_after = dict(locations_before)
        agents_after = dict(agents_before)

        move_total = 0
        gather_total = 0
        rest_total = 0
        talk_local_total = 0
        broadcast_total = 0
        propose_rule_total = 0
        vote_total = 0
        invalid_total = len(invalid_agents)
        gathered_amount_total = 0.0
        communications_emitted: list[OpenWorldCommunication] = []
        communication_influenced_action_total = 0
        trusted_influence_action_total = 0
        suspicious_discount_action_total = 0

        for agent_id in agent_ids:
            agent = agents_after[agent_id]
            action = resolved_actions[agent_id]
            if agent_id in invalid_agents:
                agents_after[agent_id] = replace(
                    agent,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                continue

            action_debug = dict(action.meta) if isinstance(action.meta, dict) else {}
            if bool(action_debug.get("communication_influenced", False)):
                communication_influenced_action_total += 1
                if str(action_debug.get("influencing_speaker_label", "")) == "trusted":
                    trusted_influence_action_total += 1
            if bool(action_debug.get("discounted_suspicious_signals", False)):
                suspicious_discount_action_total += 1

            if action.kind == "move":
                from_zone = agent.location_id
                to_zone = str(action.move_target)
                next_energy = max(0.0, float(agent.energy) - float(self.config.move_energy_cost))
                updated_agent = replace(
                    agent,
                    location_id=to_zone,
                    energy=next_energy,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                agents_after[agent_id] = updated_agent
                move_total += 1
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="move",
                        location_id=from_zone,
                        action=action,
                        valid=True,
                        reason="moved",
                        payload={
                            "from": from_zone,
                            "to": to_zone,
                            **({"decision_debug": action_debug} if action_debug else {}),
                        },
                    )
                )
                continue

            if action.kind == "gather":
                loc = locations_after[agent.location_id]
                resource_type = str(loc.meta.get("resource_type", "resource"))
                requested = (
                    float(self.config.default_gather_amount)
                    if action.amount is None
                    else float(action.amount)
                )
                actual = max(0.0, min(requested, float(loc.resource)))
                if actual <= 0.0:
                    invalid_total += 1
                    invalid_agents.add(agent_id)
                    events.append(
                        OpenWorldEvent(
                            t=t_now,
                            agent_id=agent_id,
                            kind="invalid_action",
                            location_id=agent.location_id,
                            action=action,
                            valid=False,
                            reason="resource_depleted_during_resolution",
                            payload={"resolution": "no_op"},
                        )
                    )
                    agents_after[agent_id] = replace(
                        agent,
                        last_action=OpenWorldAction(kind="rest"),
                        meta={**dict(agent.meta), "credits": float(agent.wealth)},
                    )
                    continue

                updated_location = replace(loc, resource=float(loc.resource) - actual)
                locations_after[loc.id] = updated_location

                inventory = dict(agent.inventory)
                inventory[resource_type] = float(inventory.get(resource_type, 0.0)) + actual
                credit_delta = actual * self._credit_value(resource_type)
                next_wealth = float(agent.wealth) + credit_delta
                next_energy = max(0.0, float(agent.energy) - float(self.config.gather_energy_cost))

                updated_agent = replace(
                    agent,
                    inventory=inventory,
                    wealth=next_wealth,
                    energy=next_energy,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": next_wealth},
                )
                agents_after[agent_id] = updated_agent

                gather_total += 1
                gathered_amount_total += actual
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="gather",
                        location_id=loc.id,
                        action=action,
                        valid=True,
                        reason="gathered",
                        payload={
                            "resource_type": resource_type,
                            "requested": requested,
                            "actual": actual,
                            "credits_delta": credit_delta,
                            **({"decision_debug": action_debug} if action_debug else {}),
                        },
                    )
                )
                continue

            if action.kind == "talk_local":
                communication = OpenWorldCommunication(
                    t=t_now,
                    sender_id=agent_id,
                    scope="local",
                    location_id=agent.location_id,
                    message=str(action.message or ""),
                    speech_act=str(action.speech_act or "inform"),
                    topic=str(action.topic or "resource"),
                    meta={"visibility": "same_zone"},
                )
                evidence = self._evaluate_communication_evidence(
                    communication=communication,
                    locations_snapshot=locations_after,
                )
                if evidence is not None:
                    communication = replace(
                        communication,
                        meta={**dict(communication.meta), "reputation_evidence": dict(evidence)},
                    )
                communications_emitted.append(communication)
                talk_local_total += 1
                agents_after[agent_id] = replace(
                    agent,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="talk_local",
                        location_id=agent.location_id,
                        action=action,
                        valid=True,
                        reason="spoke_local",
                        payload={"communication": communication.to_dict()},
                    )
                )
                continue

            if action.kind == "broadcast":
                bulletin = OpenWorldCommunication(
                    t=t_now,
                    sender_id=agent_id,
                    scope="public",
                    location_id=agent.location_id,
                    message=str(action.message or ""),
                    speech_act=str(action.speech_act or "inform"),
                    topic=str(action.topic or "resource"),
                    meta={"visibility": "public"},
                )
                evidence = self._evaluate_communication_evidence(
                    communication=bulletin,
                    locations_snapshot=locations_after,
                )
                if evidence is not None:
                    bulletin = replace(
                        bulletin,
                        meta={**dict(bulletin.meta), "reputation_evidence": dict(evidence)},
                    )
                communications_emitted.append(bulletin)
                broadcast_total += 1
                agents_after[agent_id] = replace(
                    agent,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="broadcast",
                        location_id=agent.location_id,
                        action=action,
                        valid=True,
                        reason="broadcasted",
                        payload={"communication": bulletin.to_dict()},
                    )
                )
                continue

            if action.kind == "propose_rule":
                try:
                    template, params = self._normalize_rule_template_and_params(
                        template=str(action.rule_template or ""),
                        params=action.rule_params,
                    )
                except ValueError as exc:
                    invalid_total += 1
                    invalid_agents.add(agent_id)
                    events.append(
                        OpenWorldEvent(
                            t=t_now,
                            agent_id=agent_id,
                            kind="invalid_action",
                            location_id=agent.location_id,
                            action=action,
                            valid=False,
                            reason=f"ValueError: {exc}",
                            payload={"resolution": "no_op"},
                        )
                    )
                    agents_after[agent_id] = replace(
                        agent,
                        last_action=OpenWorldAction(kind="rest"),
                        meta={**dict(agent.meta), "credits": float(agent.wealth)},
                    )
                    continue

                proposal_id = self._next_proposal_id()
                proposal = GovernanceProposal(
                    proposal_id=proposal_id,
                    proposer_id=agent_id,
                    template=template,
                    params=params,
                    status="proposed",
                    created_t=t_now,
                    meta={"source": "agent_action"},
                )
                self._proposals[proposal_id] = proposal
                propose_rule_total += 1
                agents_after[agent_id] = replace(
                    agent,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="propose_rule",
                        location_id=agent.location_id,
                        action=action,
                        valid=True,
                        reason="proposal_created",
                        payload={"proposal": proposal.to_dict()},
                    )
                )
                continue

            if action.kind == "vote":
                proposal = self._proposals.get(str(action.proposal_id))
                if proposal is None:
                    invalid_total += 1
                    invalid_agents.add(agent_id)
                    events.append(
                        OpenWorldEvent(
                            t=t_now,
                            agent_id=agent_id,
                            kind="invalid_action",
                            location_id=agent.location_id,
                            action=action,
                            valid=False,
                            reason="unknown_proposal_id",
                            payload={"resolution": "no_op"},
                        )
                    )
                    agents_after[agent_id] = replace(
                        agent,
                        last_action=OpenWorldAction(kind="rest"),
                        meta={**dict(agent.meta), "credits": float(agent.wealth)},
                    )
                    continue

                updated_votes = dict(proposal.votes)
                updated_votes[int(agent_id)] = str(action.vote_choice or "no")
                updated_proposal = replace(
                    proposal,
                    votes=updated_votes,
                    meta={**dict(proposal.meta), "last_vote_t": t_now},
                )
                self._proposals[proposal.proposal_id] = updated_proposal
                vote_total += 1
                agents_after[agent_id] = replace(
                    agent,
                    last_action=action,
                    meta={**dict(agent.meta), "credits": float(agent.wealth)},
                )
                events.append(
                    OpenWorldEvent(
                        t=t_now,
                        agent_id=agent_id,
                        kind="vote",
                        location_id=agent.location_id,
                        action=action,
                        valid=True,
                        reason="vote_recorded",
                        payload={
                            "proposal_id": proposal.proposal_id,
                            "vote_choice": str(action.vote_choice),
                            "votes_tally": {
                                "yes": sum(
                                    1
                                    for choice in updated_proposal.votes.values()
                                    if choice == "yes"
                                ),
                                "no": sum(
                                    1
                                    for choice in updated_proposal.votes.values()
                                    if choice == "no"
                                ),
                            },
                        },
                    )
                )
                continue

            # rest
            next_energy = min(
                float(self.config.max_energy),
                float(agent.energy) + float(self.config.rest_recovery),
            )
            agents_after[agent_id] = replace(
                agent,
                energy=next_energy,
                last_action=action,
                meta={**dict(agent.meta), "credits": float(agent.wealth)},
            )
            rest_total += 1
            events.append(
                OpenWorldEvent(
                    t=t_now,
                    agent_id=agent_id,
                    kind="rest",
                    location_id=agent.location_id,
                    action=action,
                    valid=True,
                    reason="rested",
                    payload={
                        "energy_after": next_energy,
                        **({"decision_debug": action_debug} if action_debug else {}),
                    },
                )
            )

        reputation_summary = self._update_reputation_beliefs(
            events=events,
            communications=communications_emitted,
            agents_snapshot=agents_after,
            locations_snapshot=locations_after,
        )
        governance_pending = self._sorted_pending_proposals()
        governance_active = self._sorted_active_rules()
        governance_activated_total = sum(1 for event in events if event.kind == "rule_activated")
        governance_expired_total = sum(1 for event in events if event.kind == "rule_expired")
        governance_summary = {
            "pending_proposals_count": len(governance_pending),
            "active_rules_count": len(governance_active),
            "proposal_created_total": int(propose_rule_total),
            "vote_cast_total": int(vote_total),
            "rule_activated_total": int(governance_activated_total),
            "rule_expired_total": int(governance_expired_total),
            "pending_proposals": [proposal.to_dict() for proposal in governance_pending],
            "active_rules": [rule.to_dict() for rule in governance_active],
        }

        # Regenerate resources after resolving all actions.
        for zone_id, location in list(locations_after.items()):
            regenerated = min(
                float(location.resource_cap),
                float(location.resource) + float(location.regen_rate),
            )
            locations_after[zone_id] = replace(location, resource=regenerated)

        total_resource = sum(float(location.resource) for location in locations_after.values())
        total_credits = sum(float(agent.wealth) for agent in agents_after.values())
        avg_energy = sum(float(agent.energy) for agent in agents_after.values()) / max(
            1, len(agents_after)
        )
        communication_total = int(talk_local_total + broadcast_total)

        tick = OpenWorldTick(
            t=t_now,
            locations=locations_after,
            agents=agents_after,
            events=tuple(events),
            metrics={
                "move_total": move_total,
                "gather_total": gather_total,
                "rest_total": rest_total,
                "talk_local_total": talk_local_total,
                "broadcast_total": broadcast_total,
                "propose_rule_total": propose_rule_total,
                "vote_total": vote_total,
                "communication_total": communication_total,
                "invalid_action_total": invalid_total,
                "gather_amount_total": float(gathered_amount_total),
                "total_resource": float(total_resource),
                "total_credits": float(total_credits),
                "avg_energy": float(avg_energy),
                "average_honesty_belief": float(reputation_summary["average_honesty_belief"]),
                "average_belief_confidence": float(reputation_summary["average_belief_confidence"]),
                "suspicious_labels_count": int(reputation_summary["suspicious_labels_count"]),
                "validated_truthful_reports": int(reputation_summary["validated_truthful_reports"]),
                "validated_false_reports": int(reputation_summary["validated_false_reports"]),
                "communication_influenced_action_total": int(communication_influenced_action_total),
                "trusted_influence_action_total": int(trusted_influence_action_total),
                "suspicious_discount_action_total": int(suspicious_discount_action_total),
                "governance_pending_proposals_count": int(
                    governance_summary["pending_proposals_count"]
                ),
                "governance_active_rules_count": int(governance_summary["active_rules_count"]),
                "governance_proposal_created_total": int(
                    governance_summary["proposal_created_total"]
                ),
                "governance_vote_cast_total": int(governance_summary["vote_cast_total"]),
                "governance_rule_activated_total": int(governance_summary["rule_activated_total"]),
                "governance_rule_expired_total": int(governance_summary["rule_expired_total"]),
                "collapsed": False,
            },
            info={
                "mode": "open_world",
                "update_order": [
                    "advance_governance_lifecycle",
                    "validate_actions",
                    "resolve_actions",
                    "propagate_communications",
                    "update_reputation_beliefs",
                    "regenerate_resources",
                ],
                "deterministic_agent_order": list(agent_ids),
                "zones": list(ZONE_ORDER),
                "communications_emitted": len(communications_emitted),
                "decision_influence_summary": {
                    "communication_influenced_action_total": int(
                        communication_influenced_action_total
                    ),
                    "trusted_influence_action_total": int(trusted_influence_action_total),
                    "suspicious_discount_action_total": int(suspicious_discount_action_total),
                },
                "governance_summary": governance_summary,
                "reputation_summary": {
                    "average_honesty_belief": float(reputation_summary["average_honesty_belief"]),
                    "average_belief_confidence": float(
                        reputation_summary["average_belief_confidence"]
                    ),
                    "suspicious_labels_count": int(reputation_summary["suspicious_labels_count"]),
                    "validated_truthful_reports": int(
                        reputation_summary["validated_truthful_reports"]
                    ),
                    "validated_false_reports": int(reputation_summary["validated_false_reports"]),
                    "by_observer": dict(reputation_summary["by_observer"]),
                },
            },
        )

        self.locations = locations_after
        self.agents = agents_after
        self.t = t_now + 1
        self._recent_events.extend(events)
        if len(self._recent_events) > 200:
            self._recent_events = self._recent_events[-200:]
        self._communications.extend(communications_emitted)
        if len(self._communications) > int(self.config.communication_history_limit):
            self._communications = self._communications[
                -int(self.config.communication_history_limit) :
            ]
        return tick
