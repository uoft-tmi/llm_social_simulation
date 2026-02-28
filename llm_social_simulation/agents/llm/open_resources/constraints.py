from __future__ import annotations

from dataclasses import dataclass

from llm_social_simulation.simulation.gameworld import OpenResourcesObservation


@dataclass(frozen=True)
class OpenResourcesConstraints:
    min_harvest: float
    max_harvest: float
    sustainable_harvest_cap: float
    min_contribute: float
    max_contribute: float


def constraints_from_observation(
    *,
    obs: OpenResourcesObservation,
    max_harvest_per_step: float,
    sustainable_frac: float,
    contrib_max_frac: float,
) -> OpenResourcesConstraints:
    n_agents = max(1, len(obs.known_agents))
    return OpenResourcesConstraints(
        min_harvest=0.0,
        max_harvest=float(max_harvest_per_step),
        sustainable_harvest_cap=float(sustainable_frac) * float(obs.R) / n_agents,
        min_contribute=0.0,
        max_contribute=float(contrib_max_frac) * float(obs.self_wealth),
    )
