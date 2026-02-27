from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from llm_social_simulation.simulation.gameworld import OpenResourcesObservation

from .memory import MemoryEvent


def _system_prompt() -> str:
    return (
        "You are an Open Resources simulation agent. Respond with JSON only. "
        "Do not include markdown, prose, or code fences. "
        "Required JSON schema: "
        '{"required":true,"self_id":<int>,"t":<int>,'
        '"action":{"harvest":<float>=0,"contribute":<float>=0},'
        '"reason":<string|null>}. '
        "The field required must be true."
    )


def build_open_resources_messages(
    obs: OpenResourcesObservation,
    memory_window: Sequence[MemoryEvent],
    *,
    run_id: str,
) -> tuple[Mapping[str, str], ...]:
    # --- build deterministic user payload from current state + memory ---
    user_payload = {
        "run_id": run_id,
        "agent_id": obs.self_id,
        "round": obs.t,
        "observation": {
            "self_id": obs.self_id,
            "t": obs.t,
            "R": float(obs.R),
            "P": float(obs.P),
            "self_wealth": float(obs.self_wealth),
            "known_agents": list(obs.known_agents),
            "info": dict(obs.info),
        },
        "memory_window": [event.to_prompt_item() for event in memory_window],
        "constraints": {
            "harvest_min": 0.0,
            "contribute_min": 0.0,
            "required_must_be_true": True,
        },
    }

    # --- return chat-style messages consumed by LLMRequest ---
    return (
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": json.dumps(user_payload, sort_keys=True, separators=(",", ":")),
        },
    )
