from __future__ import annotations

from typing import Literal

from llm_social_simulation.models.schema import response_format_for_schema, strict_json_parse
from llm_social_simulation.models.types import LLMParseError
from llm_social_simulation.simulation.gameworld import OpenResourcesAction

from .schema import OpenResourcesDecisionPayload, ParsedOpenResourcesDecision


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
    if payload.required is False:
        raise LLMParseError("Response required field must not be false")

    id_filled = False
    id_source: Literal["self_id", "agent_id", "fallback"] = "self_id"
    if payload.self_id is not None:
        self_id = payload.self_id
        id_source = "self_id"
    elif payload.agent_id is not None:
        self_id = payload.agent_id
        id_source = "agent_id"
    else:
        self_id = expected_agent_id
        id_filled = True
        id_source = "fallback"

    # tolerate missing id from model; fill with known agent_id
    if self_id != expected_agent_id:
        raise LLMParseError(
            f"Response self_id mismatch: expected {expected_agent_id}, got {self_id}"
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
        id_filled=id_filled,
        id_source=id_source,
    )
