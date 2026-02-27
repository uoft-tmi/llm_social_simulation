from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.types import LLMParseError, LLMRequest
from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


@dataclass(frozen=True)
class LLMOpenResourcesPolicyConfig:
    model: str
    run_id: str
    temperature: float = 0.0
    max_tokens: int = 160
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMOpenResourcesPolicy:
    """LLM-backed policy for Open Resources decisions with strict parsing."""

    def __init__(self, *, agent_id: int, client: LLMClient, config: LLMOpenResourcesPolicyConfig):
        self.agent_id = agent_id
        self.client = client
        self.config = config

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        if obs.self_id != self.agent_id:
            raise ValueError(
                f"Observation self_id {obs.self_id} does not match policy agent_id {self.agent_id}"
            )

        request = LLMRequest(
            model=self.config.model,
            messages=(
                {"role": "system", "content": "Return strict JSON decision for Open Resources."},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "self_id": obs.self_id,
                            "t": obs.t,
                            "R": obs.R,
                            "P": obs.P,
                            "self_wealth": obs.self_wealth,
                            "known_agents": list(obs.known_agents),
                        },
                        sort_keys=True,
                    ),
                },
            ),
            temperature=float(self.config.temperature),
            max_tokens=int(self.config.max_tokens),
            metadata={
                **self.config.metadata,
                "run_id": self.config.run_id,
                "agent_id": self.agent_id,
                "t": obs.t,
            },
        )
        response = self.client.generate(request)
        try:
            raw = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise LLMParseError("LLM response is not valid JSON") from exc

        if not isinstance(raw, dict):
            raise LLMParseError("LLM response must be a JSON object")

        self_id = raw.get("self_id", raw.get("agent_id"))
        t = raw.get("t")
        if self_id != self.agent_id:
            raise LLMParseError(f"self_id mismatch: expected {self.agent_id}, got {self_id}")
        if t != obs.t:
            raise LLMParseError(f"t mismatch: expected {obs.t}, got {t}")

        action = raw.get("action")
        if not isinstance(action, dict):
            raise LLMParseError("missing action object")
        if "harvest" not in action or "contribute" not in action:
            raise LLMParseError("action must include harvest and contribute")

        try:
            harvest = float(action["harvest"])
            contribute = float(action["contribute"])
        except (TypeError, ValueError) as exc:
            raise LLMParseError("harvest and contribute must be numeric") from exc

        return OpenResourcesAction(harvest=harvest, contribute=contribute)
