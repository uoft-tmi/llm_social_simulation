from __future__ import annotations

from dataclasses import dataclass

from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation

from .base import OpenResourcesPolicy


@dataclass
class GuardrailsPolicy(OpenResourcesPolicy):
    """
    Wrap an OpenResourcesPolicy and clamp its outputs to keep the simulation stable.
    """

    agent_id: int
    inner: OpenResourcesPolicy
    max_harvest_per_step: float
    sustainable_frac: float = 0.4
    contrib_max_frac: float = 0.2

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        try:
            act = self.inner.decide(obs)
        except Exception:
            return OpenResourcesAction(harvest=0.0, contribute=0.0)

        harvest = float(act.harvest)
        if harvest != harvest:
            harvest = 0.0
        harvest = max(0.0, min(harvest, float(self.max_harvest_per_step)))

        n = 1
        try:
            n = max(1, len(obs.known_agents))
        except Exception:
            n = 1
        sustainable_cap = float(self.sustainable_frac) * float(obs.R) / n
        harvest = min(harvest, sustainable_cap)

        contribute = float(act.contribute)
        if contribute != contribute:
            contribute = 0.0
        contribute = max(0.0, contribute)
        contribute = min(contribute, float(self.contrib_max_frac) * float(obs.self_wealth))

        return OpenResourcesAction(harvest=harvest, contribute=contribute)
