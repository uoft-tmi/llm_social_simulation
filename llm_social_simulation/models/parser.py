from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from llm_social_simulation.simulation.gameworld import OpenResourcesAction

from .schema import response_format_for_schema, strict_json_parse
from .types import LLMParseError


class OpenResourcesActionPayload(BaseModel):
    harvest: float = Field(ge=0.0)
    contribute: float = Field(ge=0.0)


class OpenResourcesDecisionPayload(BaseModel):
    required: Literal[True]
    self_id: int
    t: int
    action: OpenResourcesActionPayload
    reason: str | None = None


@dataclass(frozen=True)
class ParsedOpenResourcesDecision:
    action: OpenResourcesAction
    reason: str | None


def open_resources_response_format() -> dict[str, object]:
    # --- expose provider response_format matching the strict schema ---
    return response_format_for_schema(OpenResourcesDecisionPayload)


def parse_open_resources_decision(
    content: str,
    *,
    expected_agent_id: int,
    expected_t: int,
) -> ParsedOpenResourcesDecision:
    # --- parse JSON and enforce schema-level validation ---
    payload = strict_json_parse(content, OpenResourcesDecisionPayload)

    # --- enforce round/agent consistency with current observation ---
    if payload.self_id != expected_agent_id:
        raise LLMParseError(
            f"Response self_id mismatch: expected {expected_agent_id}, got {payload.self_id}"
        )
    if payload.t != expected_t:
        raise LLMParseError(f"Response t mismatch: expected {expected_t}, got {payload.t}")

    # --- convert validated payload into gameworld action type ---
    return ParsedOpenResourcesDecision(
        action=OpenResourcesAction(
            harvest=float(payload.action.harvest),
            contribute=float(payload.action.contribute),
        ),
        reason=payload.reason,
    )
