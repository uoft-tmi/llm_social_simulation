import json

from llm_social_simulation.agents.llm.open_resources.policy import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.types import LLMRequest, LLMResponse, LLMUsage
from llm_social_simulation.simulation.agents_model_based import LLMOpenResourcesAgent
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import OpenResourcesConfig, OpenResourcesGameWorld


class StructuredMockClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        agent_id = int(request.metadata["agent_id"])
        t = int(request.metadata["t"])
        content = json.dumps(
            {
                "required": True,
                "self_id": agent_id,
                "t": t,
                "action": {
                    "harvest": 1.0 + (agent_id * 0.1),
                    "contribute": 0.0,
                },
                "reason": "deterministic",
            },
            sort_keys=True,
        )
        return LLMResponse(
            content=content,
            model=f"mock:{request.model}",
            request_hash=request.stable_hash(),
            latency_ms=0.0,
            usage=LLMUsage(prompt_tokens=120, completion_tokens=50, total_tokens=170),
            raw={"source": "structured-mock"},
        )


def test_open_resources_llm_flow_runs_end_to_end() -> None:
    world = OpenResourcesGameWorld(
        OpenResourcesConfig(
            agent_ids=(0, 1),
            initial_resource=20.0,
            max_harvest_per_step=10.0,
            regen_rate=0.0,
        )
    )
    client = StructuredMockClient()

    agents = []
    for agent_id in (0, 1):
        policy = LLMOpenResourcesPolicy(
            agent_id=agent_id,
            client=client,
            config=LLMOpenResourcesPolicyConfig(
                model="unit-model",
                run_id="test-run",
                max_tokens=160,
            ),
        )
        agents.append(LLMOpenResourcesAgent(agent_id=agent_id, policy=policy))

    engine = SimulationEngine(world, agents)
    ticks = engine.run(3)

    assert len(ticks) == 3
    assert set(ticks[-1].wealth.keys()) == {0, 1}
    assert ticks[0].harvest_requested[0] == 1.0
    assert ticks[0].harvest_requested[1] == 1.1

    round_two_req_agent_zero = next(
        request
        for request in client.requests
        if request.metadata["agent_id"] == 0 and request.metadata["t"] == 2
    )
    user_payload = json.loads(round_two_req_agent_zero.messages[1]["content"])
    memory_window = user_payload["memory_window"]
    assert len(memory_window) >= 2
    assert any(isinstance(event.get("outcome"), dict) for event in memory_window)
