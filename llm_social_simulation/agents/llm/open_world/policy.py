from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.types import LLMParseError, LLMRequest
from llm_social_simulation.simulation.open_world.types import OpenWorldAction, OpenWorldObservation

from .parser import open_world_response_format, parse_open_world_decision
from .prompt import build_open_world_messages


@dataclass(frozen=True)
class LLMOpenWorldPolicyConfig:
    model: str
    run_id: str
    temperature: float = 0.0
    max_tokens: int = 220
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMOpenWorldPolicy:
    """
    LLM-backed open-world policy.

    Guardrails/fallback are intentionally handled by GuardrailsOpenWorldPolicy.
    """

    def __init__(
        self,
        *,
        agent_id: int,
        client: LLMClient,
        config: LLMOpenWorldPolicyConfig,
    ):
        self.agent_id = int(agent_id)
        self.client = client
        self.config = config
        self.llm_call_total = 0
        self.llm_response_empty_total = 0
        self.parse_retry_count = 0
        self.filled_id_count = 0
        self.last_raw_output: str | None = None
        self.last_provider: str | None = None

    def _record_response(self, content: str, raw: Any) -> None:
        self.llm_call_total += 1
        text = content if isinstance(content, str) else str(content)
        self.last_raw_output = text[:200]
        if text.strip() == "":
            self.llm_response_empty_total += 1

        provider: str | None = None
        if isinstance(raw, dict):
            raw_provider = raw.get("provider")
            if isinstance(raw_provider, dict):
                for key in ("name", "provider", "slug"):
                    value = raw_provider.get(key)
                    if isinstance(value, str) and value.strip():
                        provider = value
                        break
                if provider is None:
                    provider = str(raw_provider)
            elif isinstance(raw_provider, str):
                provider = raw_provider
        self.last_provider = provider

    def decide(self, obs: OpenWorldObservation) -> OpenWorldAction:
        if obs.self_id != self.agent_id:
            raise ValueError(
                f"Observation self_id {obs.self_id} does not match policy agent_id {self.agent_id}"
            )

        messages = build_open_world_messages(obs, run_id=self.config.run_id)
        request = LLMRequest(
            model=self.config.model,
            messages=messages,
            response_format=open_world_response_format(),
            temperature=float(self.config.temperature),
            max_tokens=int(self.config.max_tokens),
            metadata={
                **self.config.metadata,
                "mode": "open_world",
                "run_id": self.config.run_id,
                "agent_id": self.agent_id,
                "t": int(obs.t),
            },
        )
        response = self.client.generate(request)
        self._record_response(response.content, response.raw)

        try:
            parsed = parse_open_world_decision(
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
                        "Your last reply was invalid. Return one valid JSON object only, "
                        "strictly following the required schema."
                    ),
                },
            )
            retry_request = LLMRequest(
                model=self.config.model,
                messages=retry_messages,
                response_format=open_world_response_format(),
                temperature=float(self.config.temperature),
                max_tokens=int(self.config.max_tokens),
                metadata={
                    **self.config.metadata,
                    "mode": "open_world",
                    "run_id": self.config.run_id,
                    "agent_id": self.agent_id,
                    "t": int(obs.t),
                    "retry_parse": True,
                },
            )
            retry_response = self.client.generate(retry_request)
            self._record_response(retry_response.content, retry_response.raw)
            parsed = parse_open_world_decision(
                retry_response.content,
                expected_agent_id=self.agent_id,
                expected_t=obs.t,
            )

        if parsed.id_filled:
            self.filled_id_count += 1
        return parsed.action
