"""
Shared policy protocol contracts.

These protocols define the minimal `decide(obs) -> action` interface expected by
simulation runners. They keep runner wiring decoupled from concrete policy
implementations.
"""

from __future__ import annotations

from typing import Protocol

from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation
from llm_social_simulation.simulation.open_world.types import OpenWorldAction, OpenWorldObservation


class OpenResourcesPolicy(Protocol):
    agent_id: int

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction: ...


class OpenWorldPolicy(Protocol):
    agent_id: int

    def decide(self, obs: OpenWorldObservation) -> OpenWorldAction: ...


__all__ = ["OpenResourcesPolicy", "OpenWorldPolicy"]
