import json

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.policies.llm_open_resources import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.models.types import LLMRequest, LLMResponse
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld


class ZeroActionClient(LLMClient):
    def generate(self, request: LLMRequest) -> LLMResponse:
        content = json.dumps(
            {
                "required": True,
                "self_id": int(request.metadata["agent_id"]),
                "t": int(request.metadata["t"]),
                "action": {"harvest": 0.0, "contribute": 0.0},
            }
        )
        return LLMResponse(
            content=content,
            model=f"mock:{request.model}",
            request_hash=request.stable_hash(),
            latency_ms=0.0,
            usage=None,
            raw={"provider": {"name": "mock-provider"}},
        )


class EmptyThenValidClient(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            content = ""
        else:
            content = json.dumps(
                {
                    "required": True,
                    "self_id": int(request.metadata["agent_id"]),
                    "t": int(request.metadata["t"]),
                    "action": {"harvest": 1.0, "contribute": 0.0},
                }
            )
        return LLMResponse(
            content=content,
            model=f"mock:{request.model}",
            request_hash=request.stable_hash(),
            latency_ms=0.0,
            usage=None,
            raw={"provider": {"name": "mock-provider"}},
        )


def _obs():
    world = OpenResourcesGameWorld(OpenResourcesConfig(agent_ids=(0,), initial_resource=10.0))
    return world.get_observation(0)


def test_llm_policy_diagnostics_zero_action_counted() -> None:
    policy = LLMOpenResourcesPolicy(
        agent_id=0,
        client=ZeroActionClient(),
        config=LLMOpenResourcesPolicyConfig(model="unit-model", run_id="diag-zero"),
    )

    action = policy.decide(_obs())
    assert action.harvest == 0.0
    assert action.contribute == 0.0
    assert policy.llm_call_total == 1
    assert policy.llm_response_empty_total == 0
    assert policy.parsed_action_zero_total == 1
    assert policy.last_raw_output is not None
    assert policy.last_provider == "mock-provider"


def test_llm_policy_diagnostics_empty_response_counted_and_retried() -> None:
    client = EmptyThenValidClient()
    policy = LLMOpenResourcesPolicy(
        agent_id=0,
        client=client,
        config=LLMOpenResourcesPolicyConfig(model="unit-model", run_id="diag-empty"),
    )

    action = policy.decide(_obs())
    assert action.harvest == 1.0
    assert action.contribute == 0.0
    assert policy.llm_call_total == 2
    assert policy.llm_response_empty_total == 1
    assert policy.parse_retry_count == 1
