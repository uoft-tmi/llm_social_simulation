from __future__ import annotations

from llm_social_simulation.agents.llm.open_resources.guardrails import GuardrailsPolicy
from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


class _StubPolicy:
    def __init__(self, agent_id: int, contribute: float):
        self.agent_id = agent_id
        self._contribute = contribute

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        del obs
        return OpenResourcesAction(harvest=1.0, contribute=self._contribute)


def _obs() -> OpenResourcesObservation:
    return OpenResourcesObservation(
        self_id=0,
        t=0,
        R=50.0,
        P=0.0,
        self_wealth=10.0,
        known_agents=[0, 1],
        info={},
    )


def test_guardrails_contribute_clamp_bounds() -> None:
    obs = _obs()

    neg = GuardrailsPolicy(
        agent_id=0,
        inner=_StubPolicy(agent_id=0, contribute=-5.0),
        max_harvest_per_step=10.0,
        contrib_max_frac=0.2,
    )
    high = GuardrailsPolicy(
        agent_id=0,
        inner=_StubPolicy(agent_id=0, contribute=99.0),
        max_harvest_per_step=10.0,
        contrib_max_frac=0.2,
    )

    neg_act = neg.decide(obs)
    high_act = high.decide(obs)

    assert 0.0 <= neg_act.contribute <= 2.0
    assert 0.0 <= high_act.contribute <= 2.0
    assert neg_act.contribute == 0.0
    assert high_act.contribute == 2.0
    assert neg.contribute_clamp_count == 1
    assert high.contribute_clamp_count == 1
    assert neg.contribute_clamp_reason_counts["negative"] >= 1
    assert high.contribute_clamp_reason_counts["above_max_contribute"] >= 1
