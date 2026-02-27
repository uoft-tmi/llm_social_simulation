from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation

from ..client import LLMClient
from ..memory import MemoryEvent, MemoryWindowStore
from ..parser import open_resources_response_format, parse_open_resources_decision
from ..prompt_builder import build_open_resources_messages
from ..types import LLMParseError, LLMRequest
from .base import OpenResourcesPolicy


@dataclass(frozen=True)
class LLMOpenResourcesPolicyConfig:
    model: str
    run_id: str
    temperature: float = 0.0
    max_tokens: int = 220
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMOpenResourcesPolicy(OpenResourcesPolicy):
    """LLM-backed policy for Open Resources decisions with strict fail-fast behavior."""

    def __init__(
        self,
        *,
        agent_id: int,
        client: LLMClient,
        config: LLMOpenResourcesPolicyConfig,
        memory_store: MemoryWindowStore | None = None,
    ):
        self.agent_id = agent_id
        self.client = client
        self.config = config
        self.memory_store = memory_store or MemoryWindowStore()
        self.parse_retry_count = 0
        self.filled_id_count = 0

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        if obs.self_id != self.agent_id:
            raise ValueError(
                f"Observation self_id {obs.self_id} does not match policy agent_id {self.agent_id}"
            )

        memory_window = self.memory_store.get_window(self.agent_id)
        messages = build_open_resources_messages(
            obs,
            memory_window,
            run_id=self.config.run_id,
        )

        request = LLMRequest(
            model=self.config.model,
            messages=messages,
            response_format=open_resources_response_format(),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            metadata={
                **self.config.metadata,
                "run_id": self.config.run_id,
                "agent_id": self.agent_id,
                "t": obs.t,
            },
        )

        response = self.client.generate(request)

        try:
            parsed = parse_open_resources_decision(
                response.content,
                expected_agent_id=self.agent_id,
                expected_t=obs.t,
            )
        except LLMParseError:
            self.parse_retry_count += 1
            retry_messages = messages + (
                {
                    "role": "user",
                    "content": (
                        "Your last reply was invalid. Return only one valid JSON object "
                        "matching the required schema. Do not include markdown or extra text."
                    ),
                },
            )
            retry_request = LLMRequest(
                model=self.config.model,
                messages=retry_messages,
                response_format=open_resources_response_format(),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                metadata={
                    **self.config.metadata,
                    "run_id": self.config.run_id,
                    "agent_id": self.agent_id,
                    "t": obs.t,
                    "retry_parse": True,
                },
            )
            retry_response = self.client.generate(retry_request)
            parsed = parse_open_resources_decision(
                retry_response.content,
                expected_agent_id=self.agent_id,
                expected_t=obs.t,
            )

        if parsed.id_filled:
            self.filled_id_count += 1

        outcome = obs.info.get("last_step_self")
        outcome_payload = dict(outcome) if isinstance(outcome, dict) else None
        self.memory_store.append(
            self.agent_id,
            MemoryEvent(
                t=obs.t,
                R=float(obs.R),
                P=float(obs.P),
                self_wealth=float(obs.self_wealth),
                action={
                    "harvest": float(parsed.action.harvest),
                    "contribute": float(parsed.action.contribute),
                },
                outcome=outcome_payload,
                reason=parsed.reason,
            ),
        )

        return parsed.action
