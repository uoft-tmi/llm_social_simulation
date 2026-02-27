from __future__ import annotations

from llm_social_simulation.models.mock_client import MockClient
from llm_social_simulation.models.policies.guardrails import GuardrailsPolicy
from llm_social_simulation.models.policies.llm_open_resources import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


def test_llm_policy_and_guardrails_smoke() -> None:
    mock = MockClient(
        fixed_content='{"agent_id":0,"t":0,"action":{"harvest":9999,"contribute":9999},"reason":"test"}'
    )

    policy = LLMOpenResourcesPolicy(
        agent_id=0,
        client=mock,
        config=LLMOpenResourcesPolicyConfig(
            model="mock",
            run_id="test_run",
            temperature=0.0,
            max_tokens=64,
        ),
    )

    wrapped = GuardrailsPolicy(
        agent_id=0,
        inner=policy,
        max_harvest_per_step=10.0,
        sustainable_frac=0.4,
        contrib_max_frac=0.2,
    )

    obs = OpenResourcesObservation(
        t=0,
        self_id=0,
        R=60.0,
        P=0.0,
        self_wealth=10.0,
        known_agents=[0, 1, 2, 3, 4, 5],
        info={},
    )

    act = wrapped.decide(obs)
    assert isinstance(act, OpenResourcesAction)
    assert 0.0 <= act.harvest <= 4.0
    assert 0.0 <= act.contribute <= 2.0
