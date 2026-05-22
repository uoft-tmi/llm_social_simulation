from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from llm_social_simulation.simulation.open_world.types import (
    OpenWorldAction,
    OpenWorldObservation,
    ReputationBelief,
)


@dataclass
class DeterministicOpenWorldAgent:
    """
    Deterministic baseline policy for open-world MVP.

    Decision rule:
    1) low energy -> rest
    2) gather if current zone has available resource
    3) else move to neighboring zone with better resource availability
    4) else rest
    """

    agent_id: int
    low_energy_threshold: float = 3.0
    gather_amount: float = 1.0
    communication_follow_threshold: float = 0.55

    def decide(self, obs: OpenWorldObservation) -> OpenWorldAction:
        if obs.self_id != self.agent_id:
            raise ValueError(
                f"Observation self_id {obs.self_id} does not match agent_id {self.agent_id}"
            )

        governance_vote = self._governance_vote_action(obs)
        if governance_vote is not None:
            return governance_vote

        if float(obs.self_state.energy) <= float(self.low_energy_threshold):
            return OpenWorldAction(kind="rest")

        guidance = self._compute_communication_guidance(obs)
        if guidance["best_zone"] is not None:
            target_zone = str(guidance["best_zone"])
            score = float(guidance["best_score"])
            if target_zone in set(obs.move_targets) and score >= float(
                self.communication_follow_threshold
            ):
                return OpenWorldAction(
                    kind="move",
                    move_target=target_zone,
                    meta=self._decision_meta(
                        guidance,
                        reason="follow_communication_move",
                    ),
                )

            if target_zone == obs.location.id and score >= float(
                self.communication_follow_threshold
            ):
                if (
                    bool(obs.action_space.get("can_gather", True))
                    and float(obs.location.resource) > 0.0
                ):
                    resource_type = str(obs.location.meta.get("resource_type", "resource"))
                    return OpenWorldAction(
                        kind="gather",
                        gather_resource=resource_type,
                        amount=float(self.gather_amount),
                        meta=self._decision_meta(
                            guidance,
                            reason="follow_communication_gather",
                        ),
                    )

        if bool(obs.action_space.get("can_gather", True)) and float(obs.location.resource) > 0.0:
            resource_type = str(obs.location.meta.get("resource_type", "resource"))
            return OpenWorldAction(
                kind="gather",
                gather_resource=resource_type,
                amount=float(self.gather_amount),
            )

        destination = self._best_neighbor_destination(obs)
        if destination is not None:
            return OpenWorldAction(kind="move", move_target=destination)

        return OpenWorldAction(kind="rest")

    def _governance_vote_action(self, obs: OpenWorldObservation) -> OpenWorldAction | None:
        if not bool(obs.action_space.get("can_vote", False)):
            return None

        votable_ids = [str(item) for item in obs.action_space.get("votable_proposal_ids", ())]
        if not votable_ids:
            return None

        pending = {
            str(proposal.proposal_id): proposal
            for proposal in obs.pending_proposals
            if proposal.status == "voting"
        }
        for proposal_id in sorted(votable_ids):
            proposal = pending.get(proposal_id)
            if proposal is None:
                continue
            if int(proposal.proposer_id) == int(self.agent_id):
                continue

            vote = self._governance_vote_choice(obs, proposal)
            return OpenWorldAction(
                kind="vote",
                proposal_id=str(proposal.proposal_id),
                vote_choice=vote,
            )
        return None

    @staticmethod
    def _governance_vote_choice(
        obs: OpenWorldObservation,
        proposal: object,
    ) -> str:
        template = str(getattr(proposal, "template", ""))
        params = dict(getattr(proposal, "params", {}) or {})
        if template == "max_gather_per_tick":
            try:
                max_amount = float(params.get("max_amount", 0.0))
            except (TypeError, ValueError):
                return "no"
            baseline = float(obs.action_space.get("active_max_gather_per_tick", 1.0))
            return "yes" if 0.1 <= max_amount <= max(1.5, baseline * 1.5) else "no"
        if template in {"zone_restriction", "broadcast_restriction_by_zone"}:
            zone_id = str(params.get("zone_id", ""))
            return "no" if zone_id == str(obs.location.id) else "yes"
        return "no"

    def _best_neighbor_destination(self, obs: OpenWorldObservation) -> str | None:
        move_targets = set(obs.move_targets)
        if not move_targets:
            return None

        current_resource = float(obs.location.resource)
        candidates = [loc for loc in obs.nearby_locations if loc.id in move_targets]
        better = [loc for loc in candidates if float(loc.resource) > current_resource]
        if not better:
            return None

        # deterministic tie-break: highest resource, then lexical id
        best = sorted(better, key=lambda loc: (-float(loc.resource), str(loc.id)))[0]
        return str(best.id)

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

    @staticmethod
    def _speaker_weight(belief: ReputationBelief | None) -> float:
        if belief is None:
            return 0.15
        confidence = float(belief.confidence)
        if belief.label == "trusted":
            return 0.9 + 0.4 * confidence
        if belief.label == "neutral":
            return 0.4 + 0.2 * confidence
        if belief.label == "suspicious":
            return -0.6 - 0.4 * confidence
        # unknown
        return 0.15 + 0.1 * confidence

    @staticmethod
    def _band_value(band: str) -> float:
        return {
            "empty": -1.0,
            "low": -0.4,
            "medium": 0.2,
            "high": 1.0,
        }.get(str(band), 0.0)

    def _belief_by_subject(self, obs: OpenWorldObservation) -> dict[int, ReputationBelief]:
        return {int(belief.subject_id): belief for belief in obs.reputation_beliefs}

    def _compute_communication_guidance(self, obs: OpenWorldObservation) -> dict[str, Any]:
        relevant_zone_ids = {str(obs.location.id), *[str(item) for item in obs.move_targets]}
        if not relevant_zone_ids:
            return {
                "best_zone": None,
                "best_score": 0.0,
                "best_speaker_label": "unknown",
                "discounted_suspicious_signals": False,
            }

        belief_by_subject = self._belief_by_subject(obs)
        zone_scores = {zone_id: 0.0 for zone_id in relevant_zone_ids}
        discounted_suspicious_signals = False
        best_signal: dict[str, Any] = {
            "score_abs": 0.0,
            "speaker_label": "unknown",
            "zone": None,
        }

        all_comms = tuple(obs.recent_communications) + tuple(obs.public_bulletins)
        for communication in all_comms:
            zone_id = str(communication.location_id)
            if zone_id not in zone_scores:
                continue
            topic = str(communication.topic)
            belief = belief_by_subject.get(int(communication.sender_id))
            speaker_label = "unknown" if belief is None else str(belief.label)
            weight = float(self._speaker_weight(belief))
            if speaker_label == "suspicious":
                discounted_suspicious_signals = True

            delta = 0.0
            if topic == "resource_report":
                claimed_band = self._parse_resource_band_claim(communication.message)
                if claimed_band is None:
                    continue
                delta = weight * self._band_value(claimed_band)
            elif topic == "risk_alert":
                claim_risk = self._parse_risk_claim(communication.message)
                if claim_risk is None:
                    continue
                delta = weight * (-1.0 if claim_risk else 0.6)
            else:
                continue

            zone_scores[zone_id] += delta
            if abs(delta) > float(best_signal["score_abs"]):
                best_signal = {
                    "score_abs": abs(delta),
                    "speaker_label": speaker_label,
                    "zone": zone_id,
                }

        ranked = sorted(zone_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
        if not ranked:
            return {
                "best_zone": None,
                "best_score": 0.0,
                "best_speaker_label": "unknown",
                "discounted_suspicious_signals": discounted_suspicious_signals,
            }

        best_zone, best_score = ranked[0]
        return {
            "best_zone": str(best_zone),
            "best_score": float(best_score),
            "best_speaker_label": str(best_signal["speaker_label"]),
            "discounted_suspicious_signals": bool(discounted_suspicious_signals),
        }

    @staticmethod
    def _decision_meta(guidance: dict[str, Any], *, reason: str) -> dict[str, Any]:
        return {
            "communication_influenced": True,
            "influence_reason": str(reason),
            "influencing_zone": guidance.get("best_zone"),
            "influence_score": float(guidance.get("best_score", 0.0)),
            "influencing_speaker_label": str(guidance.get("best_speaker_label", "unknown")),
            "discounted_suspicious_signals": bool(
                guidance.get("discounted_suspicious_signals", False)
            ),
        }


def build_deterministic_open_world_agents(
    agent_ids: Sequence[int],
) -> list[DeterministicOpenWorldAgent]:
    return [DeterministicOpenWorldAgent(agent_id=int(agent_id)) for agent_id in sorted(agent_ids)]
