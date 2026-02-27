from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryEvent:
    t: int
    R: float
    P: float
    self_wealth: float
    action: dict[str, float]
    outcome: dict[str, float | int | bool | dict[str, bool]] | None = None
    reason: str | None = None

    def to_prompt_item(
        self,
    ) -> dict[str, Any]:
        return {
            "t": self.t,
            "R": self.R,
            "P": self.P,
            "self_wealth": self.self_wealth,
            "action": {
                "harvest": float(self.action["harvest"]),
                "contribute": float(self.action["contribute"]),
            },
            "outcome": self.outcome,
            "reason": self.reason,
        }


class MemoryWindowStore:
    """In-memory per-agent memory with round and token-aware trimming."""

    def __init__(
        self,
        *,
        max_rounds: int = 8,
        max_prompt_memory_tokens: int = 220,
    ):
        self.max_rounds = max_rounds
        self.max_prompt_memory_tokens = max_prompt_memory_tokens
        self._store: dict[int, list[MemoryEvent]] = {}

    def append(self, agent_id: int, event: MemoryEvent) -> None:
        # --- append latest event and keep only the newest max_rounds ---
        events = self._store.setdefault(agent_id, [])
        events.append(event)
        if len(events) > self.max_rounds:
            self._store[agent_id] = events[-self.max_rounds :]

    def clear(self) -> None:
        self._store.clear()

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        return max(1, math.ceil(len(text) / 4))

    def get_window(self, agent_id: int) -> list[MemoryEvent]:
        # --- start from all events available for this agent ---
        events = list(self._store.get(agent_id, []))
        if not events:
            return []

        selected_rev: list[MemoryEvent] = []
        consumed = 0

        # --- take newest events first until token budget is reached ---
        for event in reversed(events):
            payload = json.dumps(event.to_prompt_item(), sort_keys=True, separators=(",", ":"))
            est = self._estimate_text_tokens(payload)
            if selected_rev and consumed + est > self.max_prompt_memory_tokens:
                break
            if not selected_rev and est > self.max_prompt_memory_tokens:
                selected_rev.append(event)
                break
            selected_rev.append(event)
            consumed += est

        # --- restore chronological order before prompt injection ---
        return list(reversed(selected_rev))
