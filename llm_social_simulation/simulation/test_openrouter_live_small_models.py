from __future__ import annotations

import os

import pytest

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.openrouter_client import OpenRouterClient
from llm_social_simulation.models.policies.llm_open_resources import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.models.types import LLMProviderError, LLMRequest, LLMResponse
from llm_social_simulation.simulation.agents_model_based import LLMOpenResourcesAgent
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld


def _test_models() -> list[str]:
    raw = os.getenv(
        "OPENROUTER_TEST_MODELS",
        "openai/gpt-4o-mini,google/gemini-2.0-flash-001",
    )
    return [model.strip() for model in raw.split(",") if model.strip()]


class VerboseOpenRouterClient(LLMClient):
    """Thin wrapper that prints prompts and responses for live-debug visibility."""

    def __init__(self, inner: OpenRouterClient):
        self.inner = inner

    def generate(self, request: LLMRequest) -> LLMResponse:
        print("\n=== OPENROUTER REQUEST ===", flush=True)
        print(f"model: {request.model}", flush=True)
        for idx, message in enumerate(request.messages):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            print(f"[{idx}] {role}: {content}", flush=True)

        response = self.inner.generate(request)

        print("=== OPENROUTER RESPONSE ===", flush=True)
        print(response.content, flush=True)
        print(
            f"meta: model={response.model}, latency_ms={response.latency_ms:.2f}, "
            f"usage={response.usage}",
            flush=True,
        )
        return response


@pytest.mark.parametrize("model", _test_models())
def test_live_openrouter_small_model_simulation_prompt_parse_roundtrip(
    model: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    try:
        raw_client = OpenRouterClient(timeout_s=float(os.getenv("OPENROUTER_TEST_TIMEOUT_S", "60")))
    except LLMProviderError:
        pytest.skip("OpenRouter API key not configured; skipping live OpenRouter simulation test")

    world = OpenResourcesGameWorld(
        OpenResourcesConfig(
            agent_ids=(0, 1),
            initial_resource=20.0,
            initial_pool=0.0,
            initial_wealth=0.0,
            max_harvest_per_step=5.0,
            regen_rate=0.0,
        )
    )
    client = VerboseOpenRouterClient(raw_client)

    agents = []
    run_id = f"live-openrouter-{model.replace('/', '-')[:40]}"
    for agent_id in (0, 1):
        policy = LLMOpenResourcesPolicy(
            agent_id=agent_id,
            client=client,
            config=LLMOpenResourcesPolicyConfig(
                model=model,
                run_id=run_id,
                temperature=0.0,
                max_tokens=120,
            ),
        )
        agents.append(LLMOpenResourcesAgent(agent_id=agent_id, policy=policy))

    engine = SimulationEngine(world, agents)
    with capsys.disabled():
        try:
            ticks = engine.run(2)
        except LLMProviderError as exc:
            msg = str(exc)
            if "response_format" in msg or "Invalid schema" in msg:
                pytest.skip(
                    f"Model {model} does not support this strict response_format contract: {msg}"
                )
            raise

    assert len(ticks) == 2
    assert set(ticks[-1].wealth.keys()) == {0, 1}

    for tick in ticks:
        assert set(tick.harvest_requested.keys()) == {0, 1}
        assert set(tick.contribute.keys()) == {0, 1}
        assert all(value >= 0.0 for value in tick.harvest_requested.values())
        assert all(value >= 0.0 for value in tick.contribute.values())
