from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from llm_social_simulation.simulation.open_world.types import OpenWorldAction, OpenWorldObservation


@dataclass
class GuardrailsOpenWorldPolicy:
    """
    Wrap an open-world policy and sanitize outputs into valid local actions.
    """

    agent_id: int
    inner: Any
    move_energy_cost: float = 0.5
    gather_energy_cost: float = 1.0
    default_gather_amount: float = 1.0
    max_message_length: int = 160
    fail_closed_count: int = 0
    invalid_action_count: int = 0
    fallback_total: int = 0
    last_error: str | None = None

    def decide(self, obs: OpenWorldObservation) -> OpenWorldAction:
        try:
            raw_action = self.inner.decide(obs)
        except Exception as exc:
            self.fail_closed_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._fallback_action(obs, reason="inner_exception")

        try:
            action = self._coerce_action(raw_action)
            return self._sanitize_action(obs, action)
        except Exception as exc:
            self.invalid_action_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._fallback_action(obs, reason="invalid_output")

    def _coerce_action(self, raw_action: OpenWorldAction | Mapping[str, Any]) -> OpenWorldAction:
        if isinstance(raw_action, OpenWorldAction):
            return raw_action
        if isinstance(raw_action, Mapping):
            return OpenWorldAction.from_dict(raw_action)
        raise ValueError(f"Unsupported action type: {type(raw_action).__name__}")

    def _sanitize_action(
        self,
        obs: OpenWorldObservation,
        action: OpenWorldAction,
    ) -> OpenWorldAction:
        if action.kind == "move":
            energy = float(obs.self_state.energy)
            move_targets = set(obs.move_targets)
            target = str(action.move_target or "")
            if target in move_targets and energy >= float(self.move_energy_cost):
                obs.validate_action(action)
                return action
            raise ValueError("invalid_or_unaffordable_move")

        if action.kind == "gather":
            energy = float(obs.self_state.energy)
            can_gather = bool(obs.action_space.get("can_gather", True))
            if not can_gather or energy < float(self.gather_energy_cost):
                raise ValueError("gather_not_allowed")

            available = float(obs.location.resource)
            if available <= 0.0:
                raise ValueError("resource_depleted")

            resource_type = str(obs.location.meta.get("resource_type", "resource"))
            amount = (
                float(self.default_gather_amount) if action.amount is None else float(action.amount)
            )
            amount = min(max(amount, 0.01), available)
            sanitized = OpenWorldAction(
                kind="gather",
                gather_resource=resource_type,
                amount=amount,
            )
            obs.validate_action(sanitized)
            return sanitized

        if action.kind in {"talk_local", "broadcast"}:
            if action.kind == "talk_local" and not bool(
                obs.action_space.get("can_talk_local", True)
            ):
                raise ValueError("talk_local_not_allowed")
            if action.kind == "broadcast" and not bool(obs.action_space.get("can_broadcast", True)):
                raise ValueError("broadcast_not_allowed")

            message = str(action.message or "").strip()
            if not message:
                raise ValueError("empty_message")
            max_len = int(obs.action_space.get("max_message_length", self.max_message_length))
            if max_len > 0:
                message = message[:max_len]
            if not message:
                raise ValueError("empty_message_after_truncate")

            speech_act = str(action.speech_act or "inform").strip().lower() or "inform"
            topic = str(action.topic or "resource").strip().lower() or "resource"
            sanitized = OpenWorldAction(
                kind=action.kind,
                message=message,
                speech_act=speech_act,
                topic=topic,
            )
            obs.validate_action(sanitized)
            return sanitized

        if action.kind == "propose_rule":
            if not bool(obs.action_space.get("can_propose_rule", True)):
                raise ValueError("propose_rule_not_allowed")
            allowed_templates = {
                str(item)
                for item in obs.action_space.get(
                    "rule_templates",
                    (
                        "max_gather_per_tick",
                        "zone_restriction",
                        "broadcast_restriction_by_zone",
                    ),
                )
            }
            template = str(action.rule_template or "").strip().lower()
            if template not in allowed_templates:
                raise ValueError("invalid_rule_template")

            params = {} if action.rule_params is None else dict(action.rule_params)
            if template == "max_gather_per_tick":
                default_amount = float(obs.action_space.get("active_max_gather_per_tick", 1.0))
                try:
                    max_amount = float(params.get("max_amount", default_amount))
                except (TypeError, ValueError):
                    max_amount = default_amount
                max_amount = max(0.1, round(max_amount, 4))
                params = {"max_amount": max_amount}
            else:
                zone_id = str(params.get("zone_id", "")).strip()
                visible_zones = {
                    str(obs.location.id),
                    *(str(loc.id) for loc in obs.nearby_locations),
                }
                if zone_id not in visible_zones:
                    zone_id = str(obs.location.id)
                params = {"zone_id": zone_id}

            sanitized = OpenWorldAction(
                kind="propose_rule",
                rule_template=template,
                rule_params=params,
            )
            obs.validate_action(sanitized)
            return sanitized

        if action.kind == "vote":
            if not bool(obs.action_space.get("can_vote", True)):
                raise ValueError("vote_not_allowed")
            proposal_id = str(action.proposal_id or "").strip()
            allowed_ids = {str(item) for item in obs.action_space.get("votable_proposal_ids", ())}
            if proposal_id not in allowed_ids:
                raise ValueError("invalid_vote_target")
            vote_choice = str(action.vote_choice or "").strip().lower()
            if vote_choice not in {"yes", "no"}:
                raise ValueError("invalid_vote_choice")
            sanitized = OpenWorldAction(
                kind="vote",
                proposal_id=proposal_id,
                vote_choice=vote_choice,
            )
            obs.validate_action(sanitized)
            return sanitized

        # rest
        if not bool(obs.action_space.get("can_rest", True)):
            raise ValueError("rest_not_allowed")
        obs.validate_action(action)
        return action

    def _fallback_action(self, obs: OpenWorldObservation, *, reason: str) -> OpenWorldAction:
        del reason
        self.fallback_total += 1

        if bool(obs.action_space.get("can_rest", True)):
            return OpenWorldAction(kind="rest")

        can_gather = bool(obs.action_space.get("can_gather", True))
        if can_gather and float(obs.location.resource) > 0.0:
            resource_type = str(obs.location.meta.get("resource_type", "resource"))
            amount = min(float(self.default_gather_amount), float(obs.location.resource))
            if amount > 0.0:
                return OpenWorldAction(
                    kind="gather",
                    gather_resource=resource_type,
                    amount=amount,
                )

        move_targets = sorted(set(obs.move_targets))
        if move_targets:
            return OpenWorldAction(kind="move", move_target=move_targets[0])

        return OpenWorldAction(kind="rest")
