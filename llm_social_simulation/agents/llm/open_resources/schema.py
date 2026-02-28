from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from llm_social_simulation.simulation.gameworld import OpenResourcesAction


class OpenResourcesActionPayload(BaseModel):
    harvest: float = Field(ge=0.0)
    contribute: float = Field(ge=0.0)


class OpenResourcesDecisionPayload(BaseModel):
    required: bool | None = None
    self_id: int | None = None
    agent_id: int | None = None
    t: int
    action: OpenResourcesActionPayload
    reason: str | None = None


@dataclass(frozen=True)
class ParsedOpenResourcesDecision:
    action: OpenResourcesAction
    reason: str | None
    id_filled: bool = False
    id_source: Literal["self_id", "agent_id", "fallback"] = "self_id"
