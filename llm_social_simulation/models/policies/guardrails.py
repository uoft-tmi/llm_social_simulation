from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    fail_closed_count: int = 0
    harvest_nan_count: int = 0
    contribute_nan_count: int = 0
    harvest_clamp_count: int = 0
    contribute_clamp_count: int = 0
    last_error: str | None = None
    contribute_clamp_reason_counts: dict[str, int] = field(default_factory=dict)
    contribute_clamp_events: list[dict[str, Any]] = field(default_factory=list)

    def decide(self, obs: OpenResourcesObservation) -> OpenResourcesAction:
        try:
            act = self.inner.decide(obs)
        except Exception as exc:
            self.fail_closed_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return OpenResourcesAction(harvest=0.0, contribute=0.0)

        harvest = float(act.harvest)
        if harvest != harvest:
            self.harvest_nan_count += 1
            harvest = 0.0
        before_clamp_harvest = harvest
        harvest = max(0.0, min(harvest, float(self.max_harvest_per_step)))
        if harvest != before_clamp_harvest:
            self.harvest_clamp_count += 1

        n = 1
        try:
            n = max(1, len(obs.known_agents))
        except Exception:
            n = 1
        sustainable_cap = float(self.sustainable_frac) * float(obs.R) / n
        before_sustainable_cap = harvest
        harvest = min(harvest, sustainable_cap)
        if harvest != before_sustainable_cap:
            self.harvest_clamp_count += 1

        contribute = float(act.contribute)
        raw_contribute = contribute
        clamp_reasons: list[str] = []
        wealth = float(obs.self_wealth)
        max_contribute = float(self.contrib_max_frac) * wealth

        if contribute != contribute:
            self.contribute_nan_count += 1
            contribute = 0.0
            clamp_reasons.append("nan")
        if contribute < 0.0:
            clamp_reasons.append("negative")
            contribute = 0.0
        if contribute > max_contribute:
            clamp_reasons.append("above_max_contribute")
            contribute = max_contribute

        if contribute != raw_contribute:
            self.contribute_clamp_count += 1
            if not clamp_reasons:
                clamp_reasons.append("other")
            for reason in clamp_reasons:
                self.contribute_clamp_reason_counts[reason] = (
                    int(self.contribute_clamp_reason_counts.get(reason, 0)) + 1
                )

            event = {
                "t": int(obs.t),
                "before": float(raw_contribute),
                "after": float(contribute),
                "reasons": list(clamp_reasons),
                "limits": {
                    "min": 0.0,
                    "max_contribute": float(max_contribute),
                    "wealth": float(wealth),
                },
            }
            self.contribute_clamp_events.append(event)
            if len(self.contribute_clamp_events) > 50:
                self.contribute_clamp_events = self.contribute_clamp_events[-50:]

        return OpenResourcesAction(harvest=harvest, contribute=contribute)
