from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


class OpenResourcesAgent(Protocol):
    """Minimal protocol for Open Resources agents used by SimulationEngine."""

    agent_id: int

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction: ...


@dataclass
class GreedyHarvesterAgent:
    """Always requests max harvest and contributes nothing."""

    agent_id: int
    max_harvest_per_step: float

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        del obs
        return OpenResourcesAction(harvest=float(self.max_harvest_per_step), contribute=0.0)


@dataclass
class CooperativeSustainableAgent:
    """Harvest conservatively by per-capita resource and contribute from wealth."""

    agent_id: int
    max_harvest_per_step: float
    target_share: float = 0.5
    contrib_rate: float = 0.05

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        n_agents = max(len(obs.known_agents), 1)
        harvest_target = float(self.target_share) * (float(obs.R) / float(n_agents))
        harvest = min(float(self.max_harvest_per_step), max(0.0, harvest_target))
        contribute = max(0.0, float(self.contrib_rate) * float(obs.self_wealth))
        return OpenResourcesAction(harvest=float(harvest), contribute=float(contribute))


@dataclass
class ResourceAwareAdaptiveAgent:
    """Adapt harvest and contribution based on resource level fraction R/cap."""

    agent_id: int
    max_harvest_per_step: float
    low_R_frac: float = 0.25
    high_R_frac: float = 0.75
    harvest_low: float = 0.25
    harvest_high: float = 0.9
    contrib_low: float = 0.10
    contrib_high: float = 0.02
    resource_cap: float | None = None

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        cap = float(self.resource_cap) if self.resource_cap is not None else max(float(obs.R), 1.0)
        frac = float(obs.R) / cap if cap > 0.0 else 0.0

        if frac <= float(self.low_R_frac):
            harvest_frac = float(self.harvest_low)
            contrib_rate = float(self.contrib_low)
        elif frac >= float(self.high_R_frac):
            harvest_frac = float(self.harvest_high)
            contrib_rate = float(self.contrib_high)
        else:
            span = float(self.high_R_frac) - float(self.low_R_frac)
            alpha = 0.0 if span <= 0.0 else (frac - float(self.low_R_frac)) / span
            harvest_frac = float(self.harvest_low) + alpha * (
                float(self.harvest_high) - float(self.harvest_low)
            )
            contrib_rate = float(self.contrib_low) + alpha * (
                float(self.contrib_high) - float(self.contrib_low)
            )

        harvest = max(0.0, harvest_frac * float(self.max_harvest_per_step))
        contribute = max(0.0, contrib_rate * float(obs.self_wealth))
        return OpenResourcesAction(harvest=float(harvest), contribute=float(contribute))
