from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from llm_social_simulation.models.schema import response_format_for_schema, strict_json_parse
from llm_social_simulation.models.types import LLMParseError
from llm_social_simulation.simulation.open_world.types import OpenWorldAction


class OpenWorldActionPayload(BaseModel):
    kind: Literal["move", "gather", "rest", "talk_local", "broadcast", "propose_rule", "vote"]
    move_target: str | None = None
    gather_resource: str | None = None
    amount: float | None = Field(default=None, gt=0.0)
    message: str | None = None
    speech_act: str | None = None
    topic: str | None = None
    rule_template: str | None = None
    rule_params: dict[str, object] | None = None
    proposal_id: str | None = None
    vote_choice: Literal["yes", "no"] | None = None

    @model_validator(mode="after")
    def _validate_by_kind(self) -> OpenWorldActionPayload:
        if self.kind == "move":
            if not isinstance(self.move_target, str) or not self.move_target.strip():
                raise ValueError("move_target is required for move action")
            if (
                self.gather_resource is not None
                or self.amount is not None
                or self.message is not None
                or self.speech_act is not None
                or self.topic is not None
                or self.rule_template is not None
                or self.rule_params is not None
                or self.proposal_id is not None
                or self.vote_choice is not None
            ):
                raise ValueError("non-move fields must be null for move action")
            return self

        if self.kind == "gather":
            if (
                self.move_target is not None
                or self.message is not None
                or self.speech_act is not None
                or self.topic is not None
                or self.rule_template is not None
                or self.rule_params is not None
                or self.proposal_id is not None
                or self.vote_choice is not None
            ):
                raise ValueError("non-gather fields must be null for gather action")
            # allow missing gather_resource; guardrails will fill with local resource type.
            return self

        if self.kind in {"talk_local", "broadcast"}:
            if (
                self.move_target is not None
                or self.gather_resource is not None
                or self.amount is not None
                or self.rule_template is not None
                or self.rule_params is not None
                or self.proposal_id is not None
                or self.vote_choice is not None
            ):
                raise ValueError("move/gather fields must be null for communication action")
            if not isinstance(self.message, str) or not self.message.strip():
                raise ValueError("message is required for communication action")
            return self

        if self.kind == "propose_rule":
            if (
                self.move_target is not None
                or self.gather_resource is not None
                or self.amount is not None
                or self.message is not None
                or self.speech_act is not None
                or self.topic is not None
                or self.proposal_id is not None
                or self.vote_choice is not None
            ):
                raise ValueError("only rule fields are allowed for propose_rule action")
            if not isinstance(self.rule_template, str) or not self.rule_template.strip():
                raise ValueError("rule_template is required for propose_rule action")
            return self

        if self.kind == "vote":
            if (
                self.move_target is not None
                or self.gather_resource is not None
                or self.amount is not None
                or self.message is not None
                or self.speech_act is not None
                or self.topic is not None
                or self.rule_template is not None
                or self.rule_params is not None
            ):
                raise ValueError("only proposal_id/vote_choice allowed for vote action")
            if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
                raise ValueError("proposal_id is required for vote action")
            if self.vote_choice not in {"yes", "no"}:
                raise ValueError("vote_choice must be yes or no")
            return self

        if (
            self.move_target is not None
            or self.gather_resource is not None
            or self.amount is not None
            or self.message is not None
            or self.speech_act is not None
            or self.topic is not None
            or self.rule_template is not None
            or self.rule_params is not None
            or self.proposal_id is not None
            or self.vote_choice is not None
        ):
            raise ValueError("rest action must not include move/gather/communication fields")
        return self


class OpenWorldDecisionPayload(BaseModel):
    required: bool | None = None
    self_id: int | None = None
    agent_id: int | None = None
    t: int
    action: OpenWorldActionPayload
    reason: str | None = None


@dataclass(frozen=True)
class ParsedOpenWorldDecision:
    action: OpenWorldAction
    reason: str | None
    id_filled: bool = False
    id_source: Literal["self_id", "agent_id", "fallback"] = "self_id"


def open_world_response_format() -> dict[str, object]:
    return response_format_for_schema(OpenWorldDecisionPayload)


def parse_open_world_decision(
    content: str,
    *,
    expected_agent_id: int,
    expected_t: int,
) -> ParsedOpenWorldDecision:
    payload = strict_json_parse(content, OpenWorldDecisionPayload)

    if payload.required is False:
        raise LLMParseError("Response required field must not be false")

    id_filled = False
    id_source: Literal["self_id", "agent_id", "fallback"] = "self_id"
    if payload.self_id is not None:
        self_id = payload.self_id
    elif payload.agent_id is not None:
        self_id = payload.agent_id
        id_source = "agent_id"
    else:
        self_id = expected_agent_id
        id_filled = True
        id_source = "fallback"

    if self_id != expected_agent_id:
        raise LLMParseError(
            f"Response self_id mismatch: expected {expected_agent_id}, got {self_id}"
        )
    if payload.t != expected_t:
        raise LLMParseError(f"Response t mismatch: expected {expected_t}, got {payload.t}")

    action_payload = payload.action
    try:
        if action_payload.kind == "move":
            action = OpenWorldAction(kind="move", move_target=str(action_payload.move_target))
        elif action_payload.kind == "gather":
            resource = (
                str(action_payload.gather_resource)
                if (
                    isinstance(action_payload.gather_resource, str)
                    and action_payload.gather_resource
                )
                else "resource"
            )
            action = OpenWorldAction(
                kind="gather",
                gather_resource=resource,
                amount=None if action_payload.amount is None else float(action_payload.amount),
            )
        elif action_payload.kind in {"talk_local", "broadcast"}:
            action = OpenWorldAction(
                kind=action_payload.kind,
                message=str(action_payload.message or ""),
                speech_act=(
                    None if action_payload.speech_act is None else str(action_payload.speech_act)
                ),
                topic=None if action_payload.topic is None else str(action_payload.topic),
            )
        elif action_payload.kind == "propose_rule":
            action = OpenWorldAction(
                kind="propose_rule",
                rule_template=str(action_payload.rule_template or ""),
                rule_params=(
                    None if action_payload.rule_params is None else dict(action_payload.rule_params)
                ),
            )
        elif action_payload.kind == "vote":
            action = OpenWorldAction(
                kind="vote",
                proposal_id=str(action_payload.proposal_id or ""),
                vote_choice=str(action_payload.vote_choice or ""),
            )
        else:
            action = OpenWorldAction(kind="rest")
    except ValueError as exc:
        raise LLMParseError(f"Invalid action payload: {exc}") from exc

    return ParsedOpenWorldDecision(
        action=action,
        reason=payload.reason,
        id_filled=id_filled,
        id_source=id_source,
    )
