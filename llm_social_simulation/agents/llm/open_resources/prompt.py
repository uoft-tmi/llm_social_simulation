from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from llm_social_simulation.models.memory import MemoryEvent
from llm_social_simulation.simulation.gameworld import OpenResourcesObservation


def _system_prompt() -> str:
    return (
        "You are an Open Resources simulation agent. "
        "Each round has four stages: contribution, harvest allocation, "
        "governance reward, regeneration. "
        "Choose harvest and contribute for this round only. "
        "Goal: maximize long-term wealth while reducing collapse risk. "
        "Avoid repeating identical zero actions for many rounds when resource is healthy. "
        "Explore with small non-zero moves when safe "
        "(for example harvest 0.5-2.0 or contribute 0.1-1.0). "
        "Respond with JSON only (no markdown or code fences). "
        "Hard constraints: harvest >= 0 and contribute >= 0. "
        "Contribute must not exceed your current self_wealth. "
        "If R is healthy (R > 0.5), do not return harvest=0 and contribute=0 together. "
        "Prefer contribute <= 20% of self_wealth unless there is a strong reason. "
        "Required output schema: "
        '{"required":true,"self_id":<int>,"t":<int>,'
        '"action":{"harvest":<float>=0,"contribute":<float>=0},'
        '"reason":<string|null>}. '
        "The field required must be true, and self_id/t must match the input. "
        "If reason is present, keep it concise: 20 words max."
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
        "decision_task": (
            "Return action.harvest and action.contribute for this round. "
            "Prefer informative, non-degenerate actions over always "
            "returning zeros when risk is low. Keep contribute within the provided bounds."
        ),
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
            "contribute_max_by_wealth": float(obs.self_wealth),
            "recommended_contribute_cap_frac": 0.2,
            "recommended_contribute_cap": 0.2 * float(obs.self_wealth),
            "resource_healthy_threshold_for_nonzero_action": 0.5,
            "forbid_both_zero_when_resource_healthy": True,
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
