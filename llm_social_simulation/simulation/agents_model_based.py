"""
Compatibility wrapper for policy-driven Open Resources agents.

Prefer constructing policies under `llm_social_simulation.agents.*`
and passing engine-compatible objects exposing:
- `agent_id`
- `decide(obs) -> action`
"""

from __future__ import annotations

from llm_social_simulation.agents.base import OpenResourcesPolicy
from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


class LLMOpenResourcesAgent:
    """Engine-compatible agent delegating decisions to an OpenResourcesPolicy."""

    def __init__(self, agent_id: int, policy: OpenResourcesPolicy):
        self.agent_id = agent_id
        self.policy = policy

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        if obs.self_id != self.agent_id:
            raise ValueError(
                f"Observation self_id {obs.self_id} does not match agent_id {self.agent_id}"
            )
        # --- delegate decision to configured model policy ---
        return self.policy.decide(obs)
