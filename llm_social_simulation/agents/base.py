from __future__ import annotations

from typing import Protocol

from llm_social_simulation.simulation.gameworld import OpenResourcesAction, OpenResourcesObservation


class OpenResourcesPolicy(Protocol):
    agent_id: int

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction: ...
