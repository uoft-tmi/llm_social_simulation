import pytest

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.policies.llm_open_resources import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.models.types import (
    LLMParseError,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld


class ProviderErrorClient(LLMClient):
    def generate(self, request: LLMRequest) -> LLMResponse:
        del request
        raise LLMProviderError("provider down")


class InvalidJsonClient(LLMClient):
    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="not-json",
            model=f"mock:{request.model}",
            request_hash=request.stable_hash(),
            latency_ms=0.0,
            usage=None,
            raw={"source": "invalid-json"},
        )


def _obs_world() -> OpenResourcesGameWorld:
    return OpenResourcesGameWorld(OpenResourcesConfig(agent_ids=(0,), initial_resource=10.0))


def test_provider_error_propagates_fail_fast() -> None:
    world = _obs_world()
    policy = LLMOpenResourcesPolicy(
        agent_id=0,
        client=ProviderErrorClient(),
        config=LLMOpenResourcesPolicyConfig(model="unit-model", run_id="err-provider"),
    )

    with pytest.raises(LLMProviderError):
        policy.decide(world.get_observation(0))


def test_parse_error_propagates_fail_fast() -> None:
    world = _obs_world()
    policy = LLMOpenResourcesPolicy(
        agent_id=0,
        client=InvalidJsonClient(),
        config=LLMOpenResourcesPolicyConfig(model="unit-model", run_id="err-parse"),
    )

    with pytest.raises(LLMParseError):
        policy.decide(world.get_observation(0))
