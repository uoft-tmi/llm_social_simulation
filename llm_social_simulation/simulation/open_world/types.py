from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence


def _normalize_string_id(value: str, *, field_name: str) -> str:
    out = str(value).strip()
    if not out:
        raise ValueError(f"{field_name} must be a non-empty string")
    return out


def _normalize_unique_strings(values: Sequence[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw).strip()
        if not item or item in seen:
            continue
        out.append(item)
        seen.add(item)
    return tuple(out)


def _normalize_token(value: str, *, field_name: str) -> str:
    token = str(value).strip().lower()
    if not token:
        raise ValueError(f"{field_name} must be a non-empty string")
    allowed_extra = {"_", "-"}
    if any(not (ch.isalnum() or ch in allowed_extra) for ch in token):
        raise ValueError(f"{field_name} must contain only [a-z0-9_-]")
    return token


def _normalize_float_mapping(values: Mapping[str, float], *, field_name: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw_key, raw_value in values.items():
        key = _normalize_string_id(str(raw_key), field_name=f"{field_name} key")
        value = float(raw_value)
        if value < 0.0:
            raise ValueError(f"{field_name}[{key}] must be >= 0")
        out[key] = value
    return out


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


GovernanceRuleTemplate = Literal[
    "max_gather_per_tick",
    "zone_restriction",
    "broadcast_restriction_by_zone",
]
GovernanceProposalStatus = Literal["proposed", "voting", "active", "expired"]
GovernanceVoteChoice = Literal["yes", "no"]


@dataclass(frozen=True)
class LocationState:
    id: str
    resource: float
    resource_cap: float
    regen_rate: float
    neighbors: tuple[str, ...] = ()
    blocked: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        location_id = _normalize_string_id(self.id, field_name="id")
        resource = float(self.resource)
        resource_cap = float(self.resource_cap)
        regen_rate = float(self.regen_rate)
        if resource < 0.0:
            raise ValueError("resource must be >= 0")
        if resource_cap < 0.0:
            raise ValueError("resource_cap must be >= 0")
        if resource > resource_cap:
            raise ValueError("resource must be <= resource_cap")
        if regen_rate < 0.0:
            raise ValueError("regen_rate must be >= 0")

        neighbors = _normalize_unique_strings(self.neighbors)
        if location_id in neighbors:
            raise ValueError("neighbors must not include self id")

        object.__setattr__(self, "id", location_id)
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "resource_cap", resource_cap)
        object.__setattr__(self, "regen_rate", regen_rate)
        object.__setattr__(self, "neighbors", neighbors)
        object.__setattr__(self, "blocked", bool(self.blocked))
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource": self.resource,
            "resource_cap": self.resource_cap,
            "regen_rate": self.regen_rate,
            "neighbors": list(self.neighbors),
            "blocked": self.blocked,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LocationState:
        return cls(
            id=str(payload["id"]),
            resource=float(payload["resource"]),
            resource_cap=float(payload["resource_cap"]),
            regen_rate=float(payload["regen_rate"]),
            neighbors=tuple(payload.get("neighbors", ())),
            blocked=bool(payload.get("blocked", False)),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class OpenWorldAction:
    kind: Literal["move", "gather", "rest", "talk_local", "broadcast", "propose_rule", "vote"]
    move_target: str | None = None
    gather_resource: str | None = None
    amount: float | None = None
    message: str | None = None
    speech_act: str | None = None
    topic: str | None = None
    rule_template: GovernanceRuleTemplate | None = None
    rule_params: dict[str, Any] | None = None
    proposal_id: str | None = None
    vote_choice: GovernanceVoteChoice | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = str(self.kind)
        if kind not in {
            "move",
            "gather",
            "rest",
            "talk_local",
            "broadcast",
            "propose_rule",
            "vote",
        }:
            raise ValueError(f"Unsupported action kind: {kind}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "meta", dict(self.meta))

        if kind == "move":
            target = _normalize_string_id(str(self.move_target or ""), field_name="move_target")
            if self.gather_resource is not None:
                raise ValueError("gather_resource must be None for move action")
            if self.amount is not None:
                raise ValueError("amount must be None for move action")
            if self.message is not None:
                raise ValueError("message must be None for move action")
            if self.speech_act is not None:
                raise ValueError("speech_act must be None for move action")
            if self.topic is not None:
                raise ValueError("topic must be None for move action")
            if self.rule_template is not None:
                raise ValueError("rule_template must be None for move action")
            if self.rule_params is not None:
                raise ValueError("rule_params must be None for move action")
            if self.proposal_id is not None:
                raise ValueError("proposal_id must be None for move action")
            if self.vote_choice is not None:
                raise ValueError("vote_choice must be None for move action")
            object.__setattr__(self, "move_target", target)
            return

        if kind == "gather":
            if self.move_target is not None:
                raise ValueError("move_target must be None for gather action")
            resource = _normalize_string_id(
                str(self.gather_resource or "resource"),
                field_name="gather_resource",
            )
            amount = None if self.amount is None else float(self.amount)
            if amount is not None and amount <= 0.0:
                raise ValueError("amount must be > 0 for gather action")
            if self.message is not None:
                raise ValueError("message must be None for gather action")
            if self.speech_act is not None:
                raise ValueError("speech_act must be None for gather action")
            if self.topic is not None:
                raise ValueError("topic must be None for gather action")
            if self.rule_template is not None:
                raise ValueError("rule_template must be None for gather action")
            if self.rule_params is not None:
                raise ValueError("rule_params must be None for gather action")
            if self.proposal_id is not None:
                raise ValueError("proposal_id must be None for gather action")
            if self.vote_choice is not None:
                raise ValueError("vote_choice must be None for gather action")
            object.__setattr__(self, "gather_resource", resource)
            object.__setattr__(self, "amount", amount)
            return

        if kind in {"talk_local", "broadcast"}:
            if self.move_target is not None:
                raise ValueError("move_target must be None for communication action")
            if self.gather_resource is not None:
                raise ValueError("gather_resource must be None for communication action")
            if self.amount is not None:
                raise ValueError("amount must be None for communication action")
            if self.rule_template is not None:
                raise ValueError("rule_template must be None for communication action")
            if self.rule_params is not None:
                raise ValueError("rule_params must be None for communication action")
            if self.proposal_id is not None:
                raise ValueError("proposal_id must be None for communication action")
            if self.vote_choice is not None:
                raise ValueError("vote_choice must be None for communication action")
            message = str(self.message or "").strip()
            if not message:
                raise ValueError("message must be a non-empty string for communication action")
            speech_act = _normalize_token(
                str(self.speech_act or "inform"),
                field_name="speech_act",
            )
            topic = _normalize_token(str(self.topic or "resource"), field_name="topic")
            object.__setattr__(self, "message", message)
            object.__setattr__(self, "speech_act", speech_act)
            object.__setattr__(self, "topic", topic)
            return

        if kind == "propose_rule":
            if self.move_target is not None:
                raise ValueError("move_target must be None for propose_rule action")
            if self.gather_resource is not None:
                raise ValueError("gather_resource must be None for propose_rule action")
            if self.amount is not None:
                raise ValueError("amount must be None for propose_rule action")
            if self.message is not None:
                raise ValueError("message must be None for propose_rule action")
            if self.speech_act is not None:
                raise ValueError("speech_act must be None for propose_rule action")
            if self.topic is not None:
                raise ValueError("topic must be None for propose_rule action")
            if self.proposal_id is not None:
                raise ValueError("proposal_id must be None for propose_rule action")
            if self.vote_choice is not None:
                raise ValueError("vote_choice must be None for propose_rule action")

            template = _normalize_token(
                str(self.rule_template or ""),
                field_name="rule_template",
            )
            if template not in {
                "max_gather_per_tick",
                "zone_restriction",
                "broadcast_restriction_by_zone",
            }:
                raise ValueError(f"Unsupported rule_template: {template}")
            raw_params = {} if self.rule_params is None else dict(self.rule_params)
            object.__setattr__(self, "rule_template", template)
            object.__setattr__(self, "rule_params", raw_params)
            return

        if kind == "vote":
            if self.move_target is not None:
                raise ValueError("move_target must be None for vote action")
            if self.gather_resource is not None:
                raise ValueError("gather_resource must be None for vote action")
            if self.amount is not None:
                raise ValueError("amount must be None for vote action")
            if self.message is not None:
                raise ValueError("message must be None for vote action")
            if self.speech_act is not None:
                raise ValueError("speech_act must be None for vote action")
            if self.topic is not None:
                raise ValueError("topic must be None for vote action")
            if self.rule_template is not None:
                raise ValueError("rule_template must be None for vote action")
            if self.rule_params is not None:
                raise ValueError("rule_params must be None for vote action")
            proposal_id = _normalize_string_id(
                str(self.proposal_id or ""),
                field_name="proposal_id",
            )
            vote_choice = _normalize_token(
                str(self.vote_choice or ""),
                field_name="vote_choice",
            )
            if vote_choice not in {"yes", "no"}:
                raise ValueError("vote_choice must be one of {'yes', 'no'}")
            object.__setattr__(self, "proposal_id", proposal_id)
            object.__setattr__(self, "vote_choice", vote_choice)
            return

        # rest
        if self.move_target is not None:
            raise ValueError("move_target must be None for rest action")
        if self.gather_resource is not None:
            raise ValueError("gather_resource must be None for rest action")
        if self.amount is not None:
            raise ValueError("amount must be None for rest action")
        if self.message is not None:
            raise ValueError("message must be None for rest action")
        if self.speech_act is not None:
            raise ValueError("speech_act must be None for rest action")
        if self.topic is not None:
            raise ValueError("topic must be None for rest action")
        if self.rule_template is not None:
            raise ValueError("rule_template must be None for rest action")
        if self.rule_params is not None:
            raise ValueError("rule_params must be None for rest action")
        if self.proposal_id is not None:
            raise ValueError("proposal_id must be None for rest action")
        if self.vote_choice is not None:
            raise ValueError("vote_choice must be None for rest action")

    def validate_move_target(self, allowed_targets: Sequence[str]) -> None:
        if self.kind != "move":
            return
        allowed = set(_normalize_unique_strings(tuple(allowed_targets)))
        if self.move_target not in allowed:
            raise ValueError(
                f"Invalid move target: {self.move_target}. Allowed targets: {sorted(allowed)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "move_target": self.move_target,
            "gather_resource": self.gather_resource,
            "amount": self.amount,
            "message": self.message,
            "speech_act": self.speech_act,
            "topic": self.topic,
            "rule_template": self.rule_template,
            "rule_params": None if self.rule_params is None else dict(self.rule_params),
            "proposal_id": self.proposal_id,
            "vote_choice": self.vote_choice,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldAction:
        return cls(
            kind=str(payload["kind"]),
            move_target=payload.get("move_target"),
            gather_resource=payload.get("gather_resource"),
            amount=payload.get("amount"),
            message=payload.get("message"),
            speech_act=payload.get("speech_act"),
            topic=payload.get("topic"),
            rule_template=payload.get("rule_template"),
            rule_params=(
                None if payload.get("rule_params") is None else dict(payload.get("rule_params", {}))
            ),
            proposal_id=payload.get("proposal_id"),
            vote_choice=payload.get("vote_choice"),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class AgentState:
    id: int
    location_id: str
    inventory: dict[str, float]
    energy: float
    wealth: float
    persona_tag: str | None = None
    memory_summary: str | None = None
    last_action: OpenWorldAction | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        agent_id = int(self.id)
        location_id = _normalize_string_id(self.location_id, field_name="location_id")
        inventory = _normalize_float_mapping(self.inventory, field_name="inventory")
        energy = float(self.energy)
        wealth = float(self.wealth)
        if energy < 0.0:
            raise ValueError("energy must be >= 0")
        if wealth < 0.0:
            raise ValueError("wealth must be >= 0")

        object.__setattr__(self, "id", agent_id)
        object.__setattr__(self, "location_id", location_id)
        object.__setattr__(self, "inventory", inventory)
        object.__setattr__(self, "energy", energy)
        object.__setattr__(self, "wealth", wealth)
        object.__setattr__(
            self, "persona_tag", None if self.persona_tag is None else str(self.persona_tag)
        )
        object.__setattr__(
            self,
            "memory_summary",
            None if self.memory_summary is None else str(self.memory_summary),
        )
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "location_id": self.location_id,
            "inventory": dict(self.inventory),
            "energy": self.energy,
            "wealth": self.wealth,
            "persona_tag": self.persona_tag,
            "memory_summary": self.memory_summary,
            "last_action": None if self.last_action is None else self.last_action.to_dict(),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AgentState:
        raw_last_action = payload.get("last_action")
        return cls(
            id=int(payload["id"]),
            location_id=str(payload["location_id"]),
            inventory=dict(payload.get("inventory", {})),
            energy=float(payload["energy"]),
            wealth=float(payload["wealth"]),
            persona_tag=payload.get("persona_tag"),
            memory_summary=payload.get("memory_summary"),
            last_action=(
                None if raw_last_action is None else OpenWorldAction.from_dict(raw_last_action)
            ),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class ReputationBelief:
    subject_id: int
    honesty: float = 0.5
    reliability: float = 0.5
    confidence: float = 0.0
    label: Literal["unknown", "neutral", "trusted", "suspicious"] = "unknown"
    evidence_count: int = 0
    truthful_reports: int = 0
    false_reports: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        subject_id = int(self.subject_id)
        honesty = _clamp_01(self.honesty)
        reliability = _clamp_01(self.reliability)
        confidence = _clamp_01(self.confidence)
        label = str(self.label)
        if label not in {"unknown", "neutral", "trusted", "suspicious"}:
            raise ValueError(f"Unsupported reputation label: {label}")
        evidence_count = int(self.evidence_count)
        truthful_reports = int(self.truthful_reports)
        false_reports = int(self.false_reports)
        if evidence_count < 0:
            raise ValueError("evidence_count must be >= 0")
        if truthful_reports < 0:
            raise ValueError("truthful_reports must be >= 0")
        if false_reports < 0:
            raise ValueError("false_reports must be >= 0")

        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "honesty", honesty)
        object.__setattr__(self, "reliability", reliability)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "evidence_count", evidence_count)
        object.__setattr__(self, "truthful_reports", truthful_reports)
        object.__setattr__(self, "false_reports", false_reports)
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "honesty": self.honesty,
            "reliability": self.reliability,
            "confidence": self.confidence,
            "label": self.label,
            "evidence_count": self.evidence_count,
            "truthful_reports": self.truthful_reports,
            "false_reports": self.false_reports,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReputationBelief:
        return cls(
            subject_id=int(payload["subject_id"]),
            honesty=float(payload.get("honesty", 0.5)),
            reliability=float(payload.get("reliability", 0.5)),
            confidence=float(payload.get("confidence", 0.0)),
            label=str(payload.get("label", "unknown")),
            evidence_count=int(payload.get("evidence_count", 0)),
            truthful_reports=int(payload.get("truthful_reports", 0)),
            false_reports=int(payload.get("false_reports", 0)),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class GovernanceRule:
    rule_id: str
    template: GovernanceRuleTemplate
    params: dict[str, Any]
    source_proposal_id: str
    activated_t: int
    expires_t: int
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        rule_id = _normalize_string_id(self.rule_id, field_name="rule_id")
        template = _normalize_token(self.template, field_name="template")
        if template not in {
            "max_gather_per_tick",
            "zone_restriction",
            "broadcast_restriction_by_zone",
        }:
            raise ValueError(f"Unsupported governance rule template: {template}")
        source_proposal_id = _normalize_string_id(
            self.source_proposal_id,
            field_name="source_proposal_id",
        )
        activated_t = int(self.activated_t)
        expires_t = int(self.expires_t)
        if activated_t < 0:
            raise ValueError("activated_t must be >= 0")
        if expires_t <= activated_t:
            raise ValueError("expires_t must be > activated_t")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "source_proposal_id", source_proposal_id)
        object.__setattr__(self, "activated_t", activated_t)
        object.__setattr__(self, "expires_t", expires_t)
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "template": self.template,
            "params": dict(self.params),
            "source_proposal_id": self.source_proposal_id,
            "activated_t": self.activated_t,
            "expires_t": self.expires_t,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GovernanceRule:
        return cls(
            rule_id=str(payload["rule_id"]),
            template=str(payload["template"]),
            params=dict(payload.get("params", {})),
            source_proposal_id=str(payload["source_proposal_id"]),
            activated_t=int(payload["activated_t"]),
            expires_t=int(payload["expires_t"]),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class GovernanceProposal:
    proposal_id: str
    proposer_id: int
    template: GovernanceRuleTemplate
    params: dict[str, Any]
    status: GovernanceProposalStatus
    created_t: int
    voting_start_t: int | None = None
    voting_end_t: int | None = None
    activation_t: int | None = None
    expiry_t: int | None = None
    votes: dict[int, GovernanceVoteChoice] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        proposal_id = _normalize_string_id(self.proposal_id, field_name="proposal_id")
        proposer_id = int(self.proposer_id)
        template = _normalize_token(self.template, field_name="template")
        if template not in {
            "max_gather_per_tick",
            "zone_restriction",
            "broadcast_restriction_by_zone",
        }:
            raise ValueError(f"Unsupported governance proposal template: {template}")
        status = _normalize_token(self.status, field_name="status")
        if status not in {"proposed", "voting", "active", "expired"}:
            raise ValueError(f"Unsupported governance proposal status: {status}")
        created_t = int(self.created_t)
        if created_t < 0:
            raise ValueError("created_t must be >= 0")

        votes: dict[int, GovernanceVoteChoice] = {}
        for raw_agent_id, raw_vote in dict(self.votes).items():
            voter_id = int(raw_agent_id)
            vote = _normalize_token(str(raw_vote), field_name="vote_choice")
            if vote not in {"yes", "no"}:
                raise ValueError("votes must be one of {'yes', 'no'}")
            votes[voter_id] = vote

        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "proposer_id", proposer_id)
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_t", created_t)
        object.__setattr__(
            self,
            "voting_start_t",
            None if self.voting_start_t is None else int(self.voting_start_t),
        )
        object.__setattr__(
            self,
            "voting_end_t",
            None if self.voting_end_t is None else int(self.voting_end_t),
        )
        object.__setattr__(
            self,
            "activation_t",
            None if self.activation_t is None else int(self.activation_t),
        )
        object.__setattr__(
            self,
            "expiry_t",
            None if self.expiry_t is None else int(self.expiry_t),
        )
        object.__setattr__(self, "votes", votes)
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "proposer_id": self.proposer_id,
            "template": self.template,
            "params": dict(self.params),
            "status": self.status,
            "created_t": self.created_t,
            "voting_start_t": self.voting_start_t,
            "voting_end_t": self.voting_end_t,
            "activation_t": self.activation_t,
            "expiry_t": self.expiry_t,
            "votes": {str(agent_id): vote for agent_id, vote in self.votes.items()},
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GovernanceProposal:
        raw_votes = dict(payload.get("votes", {}))
        votes = {int(agent_id): str(vote) for agent_id, vote in raw_votes.items()}
        return cls(
            proposal_id=str(payload["proposal_id"]),
            proposer_id=int(payload["proposer_id"]),
            template=str(payload["template"]),
            params=dict(payload.get("params", {})),
            status=str(payload.get("status", "proposed")),
            created_t=int(payload["created_t"]),
            voting_start_t=payload.get("voting_start_t"),
            voting_end_t=payload.get("voting_end_t"),
            activation_t=payload.get("activation_t"),
            expiry_t=payload.get("expiry_t"),
            votes=votes,
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class OpenWorldCommunication:
    t: int
    sender_id: int
    scope: Literal["local", "public"]
    location_id: str
    message: str
    speech_act: str = "inform"
    topic: str = "resource"
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        t = int(self.t)
        if t < 0:
            raise ValueError("t must be >= 0")
        sender_id = int(self.sender_id)
        scope = str(self.scope)
        if scope not in {"local", "public"}:
            raise ValueError(f"Unsupported communication scope: {scope}")
        location_id = _normalize_string_id(self.location_id, field_name="location_id")
        message = str(self.message).strip()
        if not message:
            raise ValueError("message must be a non-empty string")
        speech_act = _normalize_token(self.speech_act, field_name="speech_act")
        topic = _normalize_token(self.topic, field_name="topic")

        object.__setattr__(self, "t", t)
        object.__setattr__(self, "sender_id", sender_id)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "location_id", location_id)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "speech_act", speech_act)
        object.__setattr__(self, "topic", topic)
        object.__setattr__(self, "meta", dict(self.meta))

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "sender_id": self.sender_id,
            "scope": self.scope,
            "location_id": self.location_id,
            "message": self.message,
            "speech_act": self.speech_act,
            "topic": self.topic,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldCommunication:
        return cls(
            t=int(payload["t"]),
            sender_id=int(payload["sender_id"]),
            scope=str(payload["scope"]),
            location_id=str(payload["location_id"]),
            message=str(payload["message"]),
            speech_act=str(payload.get("speech_act", "inform")),
            topic=str(payload.get("topic", "resource")),
            meta=dict(payload.get("meta", {})),
        )


@dataclass(frozen=True)
class OpenWorldEvent:
    t: int
    agent_id: int
    kind: Literal[
        "move",
        "gather",
        "rest",
        "talk_local",
        "broadcast",
        "propose_rule",
        "vote",
        "rule_activated",
        "rule_expired",
        "invalid_action",
    ]
    location_id: str
    action: OpenWorldAction | None = None
    valid: bool = True
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        t = int(self.t)
        if t < 0:
            raise ValueError("t must be >= 0")
        agent_id = int(self.agent_id)
        kind = str(self.kind)
        if kind not in {
            "move",
            "gather",
            "rest",
            "talk_local",
            "broadcast",
            "propose_rule",
            "vote",
            "rule_activated",
            "rule_expired",
            "invalid_action",
        }:
            raise ValueError(f"Unsupported event kind: {kind}")
        location_id = _normalize_string_id(self.location_id, field_name="location_id")
        valid = bool(self.valid)

        if kind == "invalid_action":
            valid = False
        if not valid and not (isinstance(self.reason, str) and self.reason.strip()):
            raise ValueError("Invalid events must include a reason")

        if (
            self.action is not None
            and kind
            in {"move", "gather", "rest", "talk_local", "broadcast", "propose_rule", "vote"}
            and self.action.kind != kind
        ):
            raise ValueError("event kind/action kind mismatch")

        object.__setattr__(self, "t", t)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "location_id", location_id)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "reason", None if self.reason is None else str(self.reason))
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "agent_id": self.agent_id,
            "kind": self.kind,
            "location_id": self.location_id,
            "action": None if self.action is None else self.action.to_dict(),
            "valid": self.valid,
            "reason": self.reason,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldEvent:
        raw_action = payload.get("action")
        return cls(
            t=int(payload["t"]),
            agent_id=int(payload["agent_id"]),
            kind=str(payload["kind"]),
            location_id=str(payload["location_id"]),
            action=None if raw_action is None else OpenWorldAction.from_dict(raw_action),
            valid=bool(payload.get("valid", True)),
            reason=payload.get("reason"),
            payload=dict(payload.get("payload", {})),
        )


@dataclass(frozen=True)
class OpenWorldObservation:
    self_id: int
    t: int
    self_state: AgentState
    location: LocationState
    nearby_locations: tuple[LocationState, ...] = ()
    nearby_agents: tuple[AgentState, ...] = ()
    recent_events: tuple[OpenWorldEvent, ...] = ()
    recent_communications: tuple[OpenWorldCommunication, ...] = ()
    public_bulletins: tuple[OpenWorldCommunication, ...] = ()
    reputation_beliefs: tuple[ReputationBelief, ...] = ()
    pending_proposals: tuple[GovernanceProposal, ...] = ()
    active_rules: tuple[GovernanceRule, ...] = ()
    action_space: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self_id = int(self.self_id)
        t = int(self.t)
        if t < 0:
            raise ValueError("t must be >= 0")
        if self.self_state.id != self_id:
            raise ValueError("self_id must match self_state.id")
        if self.self_state.location_id != self.location.id:
            raise ValueError("self_state.location_id must match observation.location.id")

        nearby_locations = tuple(self.nearby_locations)
        nearby_agents = tuple(self.nearby_agents)
        recent_events = tuple(self.recent_events)
        recent_communications = tuple(self.recent_communications)
        public_bulletins = tuple(self.public_bulletins)
        reputation_beliefs = tuple(self.reputation_beliefs)
        pending_proposals = tuple(self.pending_proposals)
        active_rules = tuple(self.active_rules)

        local_location_ids = {self.location.id, *(loc.id for loc in nearby_locations)}
        for agent in nearby_agents:
            if agent.id == self_id:
                raise ValueError("nearby_agents must not include self agent")
            if agent.location_id not in local_location_ids:
                raise ValueError("nearby_agents contains far-away agent information")

        for event in recent_events:
            if event.location_id not in local_location_ids:
                raise ValueError("recent_events contains far-away event information")

        for communication in recent_communications:
            if communication.scope != "local":
                raise ValueError(
                    "recent_communications must contain local-scope communication only"
                )
            if communication.location_id != self.location.id:
                raise ValueError("recent_communications must be in the current location only")

        for bulletin in public_bulletins:
            if bulletin.scope != "public":
                raise ValueError("public_bulletins must contain public-scope communication only")

        seen_subject_ids: set[int] = set()
        for belief in reputation_beliefs:
            if belief.subject_id == self_id:
                raise ValueError("reputation_beliefs must not include self")
            if belief.subject_id in seen_subject_ids:
                raise ValueError("reputation_beliefs must contain unique subject_id values")
            seen_subject_ids.add(belief.subject_id)

        seen_proposal_ids: set[str] = set()
        for proposal in pending_proposals:
            if proposal.proposal_id in seen_proposal_ids:
                raise ValueError("pending_proposals must contain unique proposal_id values")
            seen_proposal_ids.add(proposal.proposal_id)
            if proposal.status not in {"proposed", "voting"}:
                raise ValueError("pending_proposals must only include proposed or voting items")

        seen_rule_ids: set[str] = set()
        for rule in active_rules:
            if rule.rule_id in seen_rule_ids:
                raise ValueError("active_rules must contain unique rule_id values")
            seen_rule_ids.add(rule.rule_id)

        action_space = dict(self.action_space)
        move_targets_raw = action_space.get("move_targets", list(self.location.neighbors))
        move_targets = _normalize_unique_strings(tuple(str(item) for item in move_targets_raw))
        allowed_neighbor_ids = set(self.location.neighbors)
        for target in move_targets:
            if target not in allowed_neighbor_ids:
                raise ValueError("action_space.move_targets must be neighbors of current location")

        action_space["move_targets"] = list(move_targets)
        action_space.setdefault("can_gather", True)
        action_space.setdefault("can_rest", True)
        action_space.setdefault("can_talk_local", True)
        action_space.setdefault("can_broadcast", True)
        action_space.setdefault("can_propose_rule", True)
        action_space.setdefault("can_vote", False)
        action_space.setdefault("max_message_length", 160)
        action_space.setdefault(
            "rule_templates",
            [
                "max_gather_per_tick",
                "zone_restriction",
                "broadcast_restriction_by_zone",
            ],
        )
        action_space.setdefault("votable_proposal_ids", [])

        object.__setattr__(self, "self_id", self_id)
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "nearby_locations", nearby_locations)
        object.__setattr__(self, "nearby_agents", nearby_agents)
        object.__setattr__(self, "recent_events", recent_events)
        object.__setattr__(self, "recent_communications", recent_communications)
        object.__setattr__(self, "public_bulletins", public_bulletins)
        object.__setattr__(self, "reputation_beliefs", reputation_beliefs)
        object.__setattr__(self, "pending_proposals", pending_proposals)
        object.__setattr__(self, "active_rules", active_rules)
        object.__setattr__(self, "action_space", action_space)
        object.__setattr__(self, "info", dict(self.info))

    @property
    def move_targets(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.action_space.get("move_targets", ()))

    def validate_action(self, action: OpenWorldAction) -> None:
        if action.kind == "move":
            action.validate_move_target(self.move_targets)
            return
        if action.kind == "gather" and not bool(self.action_space.get("can_gather", True)):
            raise ValueError("gather is disabled in this observation")
        if action.kind == "rest" and not bool(self.action_space.get("can_rest", True)):
            raise ValueError("rest is disabled in this observation")
        if action.kind == "talk_local" and not bool(self.action_space.get("can_talk_local", True)):
            raise ValueError("talk_local is disabled in this observation")
        if action.kind == "broadcast" and not bool(self.action_space.get("can_broadcast", True)):
            raise ValueError("broadcast is disabled in this observation")
        if action.kind == "propose_rule" and not bool(
            self.action_space.get("can_propose_rule", True)
        ):
            raise ValueError("propose_rule is disabled in this observation")
        if action.kind == "vote":
            if not bool(self.action_space.get("can_vote", True)):
                raise ValueError("vote is disabled in this observation")
            votable_ids = {str(item) for item in self.action_space.get("votable_proposal_ids", ())}
            if action.proposal_id not in votable_ids:
                raise ValueError(
                    "vote target is not in observation action_space.votable_proposal_ids"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "self_id": self.self_id,
            "t": self.t,
            "self_state": self.self_state.to_dict(),
            "location": self.location.to_dict(),
            "nearby_locations": [loc.to_dict() for loc in self.nearby_locations],
            "nearby_agents": [agent.to_dict() for agent in self.nearby_agents],
            "recent_events": [event.to_dict() for event in self.recent_events],
            "recent_communications": [
                communication.to_dict() for communication in self.recent_communications
            ],
            "public_bulletins": [bulletin.to_dict() for bulletin in self.public_bulletins],
            "reputation_beliefs": [belief.to_dict() for belief in self.reputation_beliefs],
            "pending_proposals": [proposal.to_dict() for proposal in self.pending_proposals],
            "active_rules": [rule.to_dict() for rule in self.active_rules],
            "action_space": dict(self.action_space),
            "info": dict(self.info),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldObservation:
        return cls(
            self_id=int(payload["self_id"]),
            t=int(payload["t"]),
            self_state=AgentState.from_dict(payload["self_state"]),
            location=LocationState.from_dict(payload["location"]),
            nearby_locations=tuple(
                LocationState.from_dict(item) for item in payload.get("nearby_locations", ())
            ),
            nearby_agents=tuple(
                AgentState.from_dict(item) for item in payload.get("nearby_agents", ())
            ),
            recent_events=tuple(
                OpenWorldEvent.from_dict(item) for item in payload.get("recent_events", ())
            ),
            recent_communications=tuple(
                OpenWorldCommunication.from_dict(item)
                for item in payload.get("recent_communications", ())
            ),
            public_bulletins=tuple(
                OpenWorldCommunication.from_dict(item)
                for item in payload.get("public_bulletins", ())
            ),
            reputation_beliefs=tuple(
                ReputationBelief.from_dict(item) for item in payload.get("reputation_beliefs", ())
            ),
            pending_proposals=tuple(
                GovernanceProposal.from_dict(item) for item in payload.get("pending_proposals", ())
            ),
            active_rules=tuple(
                GovernanceRule.from_dict(item) for item in payload.get("active_rules", ())
            ),
            action_space=dict(payload.get("action_space", {})),
            info=dict(payload.get("info", {})),
        )


@dataclass(frozen=True)
class OpenWorldTick:
    t: int
    locations: dict[str, LocationState]
    agents: dict[int, AgentState]
    events: tuple[OpenWorldEvent, ...]
    metrics: dict[str, float | int | bool]
    info: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        t = int(self.t)
        if t < 0:
            raise ValueError("t must be >= 0")

        locations = {str(k): v for k, v in self.locations.items()}
        for location_id, location in locations.items():
            if location_id != location.id:
                raise ValueError("location dict key must match LocationState.id")

        agents = {int(k): v for k, v in self.agents.items()}
        for agent_id, agent in agents.items():
            if agent_id != agent.id:
                raise ValueError("agent dict key must match AgentState.id")
            if agent.location_id not in locations:
                raise ValueError(
                    f"Agent {agent.id} references unknown location_id '{agent.location_id}'"
                )

        events = tuple(self.events)
        metrics = dict(self.metrics)
        info = dict(self.info)

        object.__setattr__(self, "t", t)
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "agents", agents)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "info", info)

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "locations": {loc_id: loc.to_dict() for loc_id, loc in self.locations.items()},
            "agents": {str(agent_id): agent.to_dict() for agent_id, agent in self.agents.items()},
            "events": [event.to_dict() for event in self.events],
            "metrics": dict(self.metrics),
            "info": dict(self.info),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldTick:
        return cls(
            t=int(payload["t"]),
            locations={
                str(loc_id): LocationState.from_dict(loc_payload)
                for loc_id, loc_payload in dict(payload["locations"]).items()
            },
            agents={
                int(agent_id): AgentState.from_dict(agent_payload)
                for agent_id, agent_payload in dict(payload["agents"]).items()
            },
            events=tuple(
                OpenWorldEvent.from_dict(event_payload)
                for event_payload in payload.get("events", ())
            ),
            metrics=dict(payload.get("metrics", {})),
            info=dict(payload.get("info", {})),
        )
