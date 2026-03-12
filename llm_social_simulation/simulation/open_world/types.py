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


def _normalize_float_mapping(values: Mapping[str, float], *, field_name: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw_key, raw_value in values.items():
        key = _normalize_string_id(str(raw_key), field_name=f"{field_name} key")
        value = float(raw_value)
        if value < 0.0:
            raise ValueError(f"{field_name}[{key}] must be >= 0")
        out[key] = value
    return out


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
    kind: Literal["move", "gather", "rest"]
    move_target: str | None = None
    gather_resource: str | None = None
    amount: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = str(self.kind)
        if kind not in {"move", "gather", "rest"}:
            raise ValueError(f"Unsupported action kind: {kind}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "meta", dict(self.meta))

        if kind == "move":
            target = _normalize_string_id(str(self.move_target or ""), field_name="move_target")
            if self.gather_resource is not None:
                raise ValueError("gather_resource must be None for move action")
            if self.amount is not None:
                raise ValueError("amount must be None for move action")
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
            object.__setattr__(self, "gather_resource", resource)
            object.__setattr__(self, "amount", amount)
            return

        # rest
        if self.move_target is not None:
            raise ValueError("move_target must be None for rest action")
        if self.gather_resource is not None:
            raise ValueError("gather_resource must be None for rest action")
        if self.amount is not None:
            raise ValueError("amount must be None for rest action")

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
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OpenWorldAction:
        return cls(
            kind=str(payload["kind"]),
            move_target=payload.get("move_target"),
            gather_resource=payload.get("gather_resource"),
            amount=payload.get("amount"),
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
class OpenWorldEvent:
    t: int
    agent_id: int
    kind: Literal["move", "gather", "rest", "invalid_action"]
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
        if kind not in {"move", "gather", "rest", "invalid_action"}:
            raise ValueError(f"Unsupported event kind: {kind}")
        location_id = _normalize_string_id(self.location_id, field_name="location_id")
        valid = bool(self.valid)

        if kind == "invalid_action":
            valid = False
        if not valid and not (isinstance(self.reason, str) and self.reason.strip()):
            raise ValueError("Invalid events must include a reason")

        if (
            self.action is not None
            and kind in {"move", "gather", "rest"}
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

        local_location_ids = {self.location.id, *(loc.id for loc in nearby_locations)}
        for agent in nearby_agents:
            if agent.id == self_id:
                raise ValueError("nearby_agents must not include self agent")
            if agent.location_id not in local_location_ids:
                raise ValueError("nearby_agents contains far-away agent information")

        for event in recent_events:
            if event.location_id not in local_location_ids:
                raise ValueError("recent_events contains far-away event information")

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

        object.__setattr__(self, "self_id", self_id)
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "nearby_locations", nearby_locations)
        object.__setattr__(self, "nearby_agents", nearby_agents)
        object.__setattr__(self, "recent_events", recent_events)
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "self_id": self.self_id,
            "t": self.t,
            "self_state": self.self_state.to_dict(),
            "location": self.location.to_dict(),
            "nearby_locations": [loc.to_dict() for loc in self.nearby_locations],
            "nearby_agents": [agent.to_dict() for agent in self.nearby_agents],
            "recent_events": [event.to_dict() for event in self.recent_events],
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
