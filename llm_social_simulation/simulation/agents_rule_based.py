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
    agent_id: int
    max_harvest_per_step: float
    resource_cap: float
    regen_rate: float
    regen_mode: str = "logistic"
    safety: float = 0.8
    contrib_rate: float = 0.02
    min_resource_frac: float = 0.05

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        n = max(1, len(obs.known_agents))
        R = max(0.0, float(obs.R))
        K = max(float(self.resource_cap), 1e-9)
        r = max(0.0, float(self.regen_rate))

        frac = R / K

        # hard brake when very low resource
        if frac <= self.min_resource_frac:
            harvest = 0.0
        else:
            if self.regen_mode == "logistic":
                regen = r * R * max(0.0, 1.0 - frac)
            elif self.regen_mode == "linear":
                regen = r * max(0.0, K - R)
            else:
                raise ValueError(f"Unsupported regen_mode: {self.regen_mode}")

            total_harvest = self.safety * regen
            harvest = total_harvest / n

        harvest = min(self.max_harvest_per_step, max(0.0, float(harvest)))

        contribute = self.contrib_rate * float(obs.self_wealth)
        contribute = min(max(0.0, contribute), float(obs.self_wealth))

        return OpenResourcesAction(harvest=harvest, contribute=contribute)


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
