from __future__ import annotations

import json

import pytest

from llm_social_simulation.agents.llm.open_world.guardrails import GuardrailsOpenWorldPolicy
from llm_social_simulation.agents.llm.open_world.parser import parse_open_world_decision
from llm_social_simulation.agents.llm.open_world.prompt import build_open_world_messages
from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.types import LLMParseError, LLMRequest, LLMResponse
from llm_social_simulation.simulation.open_world.runner import run_open_world_baseline
from llm_social_simulation.simulation.open_world.types import (
    AgentState,
    LocationState,
    OpenWorldObservation,
    ReputationBelief,
)


def _observation() -> OpenWorldObservation:
    location = LocationState(
        id="housing",
        resource=4.0,
        resource_cap=10.0,
        regen_rate=0.5,
        neighbors=("farm", "forest"),
        blocked=False,
        meta={"resource_type": "labor"},
    )
    nearby_locations = (
        LocationState(
            id="farm",
            resource=6.0,
            resource_cap=10.0,
            regen_rate=0.5,
            neighbors=(),
            blocked=False,
            meta={"resource_type": "grain", "coarse": True, "resource_band": "medium"},
        ),
        LocationState(
            id="forest",
            resource=2.0,
            resource_cap=10.0,
            regen_rate=0.5,
            neighbors=(),
            blocked=False,
            meta={"resource_type": "wood", "coarse": True, "resource_band": "low"},
        ),
    )
    self_state = AgentState(
        id=0,
        location_id="housing",
        inventory={"labor": 1.0},
        energy=8.0,
        wealth=3.0,
    )
    return OpenWorldObservation(
        self_id=0,
        t=3,
        self_state=self_state,
        location=location,
        nearby_locations=nearby_locations,
        nearby_agents=(),
        recent_events=(),
        reputation_beliefs=(
            ReputationBelief(
                subject_id=7,
                honesty=0.8,
                reliability=0.75,
                confidence=0.6,
                label="trusted",
            ),
        ),
        action_space={"move_targets": ["farm", "forest"], "can_gather": True, "can_rest": True},
        info={"mode": "open_world"},
    )


def test_open_world_prompt_is_structured_and_local() -> None:
    obs = _observation()
    messages = build_open_world_messages(obs, run_id="ow-run-1")

    assert messages[0]["role"] == "system"
    assert "talk_local" in messages[0]["content"]
    assert "propose_rule" in messages[0]["content"]
    assert "vote" in messages[0]["content"]
    assert "Calibrate trust using visible reputation beliefs" in messages[0]["content"]

    payload = json.loads(messages[1]["content"])
    assert payload["observation"]["self_id"] == 0
    assert payload["observation"]["location"]["id"] == "housing"
    assert [loc["id"] for loc in payload["observation"]["nearby_locations"]] == ["farm", "forest"]
    assert payload["constraints"]["move_targets"] == ["farm", "forest"]
    assert payload["constraints"]["gather_resource_type"] == "labor"
    assert "talk_local" in payload["constraints"]["allowed_actions"]
    assert "broadcast" in payload["constraints"]["allowed_actions"]
    assert "propose_rule" in payload["constraints"]["allowed_actions"]
    assert "vote" in payload["constraints"]["allowed_actions"]
    assert payload["observation"]["reputation_beliefs"][0]["subject_id"] == 7
    assert payload["observation"]["reputation_beliefs"][0]["label"] == "trusted"
    assert payload["constraints"]["trust_calibration_hint"]["trusted_label"] == "higher_weight"
    assert "pending_proposals" in payload["observation"]
    assert "active_rules" in payload["observation"]


def test_open_world_parser_success_and_failure() -> None:
    ok = (
        '{"required":true,"self_id":0,"t":3,'
        '"action":{"kind":"move","move_target":"farm"},"reason":"move to richer zone"}'
    )
    parsed = parse_open_world_decision(ok, expected_agent_id=0, expected_t=3)
    assert parsed.action.kind == "move"
    assert parsed.action.move_target == "farm"

    talk = (
        '{"required":true,"self_id":0,"t":3,'
        '"action":{"kind":"talk_local","message":"need help",'
        '"speech_act":"request","topic":"coordination"}}'
    )
    parsed_talk = parse_open_world_decision(talk, expected_agent_id=0, expected_t=3)
    assert parsed_talk.action.kind == "talk_local"
    assert parsed_talk.action.message == "need help"
    assert parsed_talk.action.speech_act == "request"
    assert parsed_talk.action.topic == "coordination"

    bad = '{"required":true,"self_id":0,"t":3,"action":{"kind":"move"}}'
    with pytest.raises(LLMParseError):
        parse_open_world_decision(bad, expected_agent_id=0, expected_t=3)

    bad_comm = '{"required":true,"self_id":0,"t":3,"action":{"kind":"broadcast","message":"  "}}'
    with pytest.raises(LLMParseError):
        parse_open_world_decision(bad_comm, expected_agent_id=0, expected_t=3)

    propose = (
        '{"required":true,"self_id":0,"t":3,'
        '"action":{"kind":"propose_rule","rule_template":"max_gather_per_tick",'
        '"rule_params":{"max_amount":1.0}}}'
    )
    parsed_propose = parse_open_world_decision(propose, expected_agent_id=0, expected_t=3)
    assert parsed_propose.action.kind == "propose_rule"
    assert parsed_propose.action.rule_template == "max_gather_per_tick"

    vote = (
        '{"required":true,"self_id":0,"t":3,'
        '"action":{"kind":"vote","proposal_id":"proposal_0001","vote_choice":"yes"}}'
    )
    parsed_vote = parse_open_world_decision(vote, expected_agent_id=0, expected_t=3)
    assert parsed_vote.action.kind == "vote"
    assert parsed_vote.action.proposal_id == "proposal_0001"


class _InvalidMoveInner:
    def __init__(self, agent_id: int):
        self.agent_id = int(agent_id)

    def decide(self, obs: OpenWorldObservation) -> dict[str, str]:
        del obs
        return {"kind": "broadcast", "message": "   "}


def test_open_world_guardrails_fallback_on_invalid_action() -> None:
    policy = GuardrailsOpenWorldPolicy(agent_id=0, inner=_InvalidMoveInner(agent_id=0))
    action = policy.decide(_observation())

    assert action.kind == "rest"
    assert policy.invalid_action_count == 1
    assert policy.fallback_total == 1


class _MockOpenWorldClient(LLMClient):
    def generate(self, request: LLMRequest) -> LLMResponse:
        agent_id = int(request.metadata.get("agent_id", 0))
        t = int(request.metadata.get("t", 0))
        content = json.dumps(
            {
                "required": True,
                "self_id": agent_id,
                "t": t,
                "action": {
                    "kind": "talk_local",
                    "message": "resource looks healthy",
                    "speech_act": "inform",
                    "topic": "resource",
                },
                "reason": "share local signal",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return LLMResponse(
            content=content,
            model="mock/open-world",
            request_hash=request.stable_hash(),
            latency_ms=1.0,
            usage=None,
            raw={"provider": {"name": "mock"}},
        )


def test_open_world_llm_smoke_with_mock_client() -> None:
    ticks, summary = run_open_world_baseline(
        n_agents=3,
        rounds=5,
        seed=0,
        agent_type="llm",
        llm_guardrails=True,
        llm_model="mock/open-world",
        llm_client=_MockOpenWorldClient(),
    )

    assert len(ticks) == 5
    assert summary["mode"] == "open_world"
    assert summary["params"]["agent_type"] == "llm"
    assert summary["llm_diagnostics"]["llm_call_total"] == 15
    assert summary["llm_diagnostics"]["guardrails_fallback_total"] == 0
    assert all(int(tick.metrics["invalid_action_total"]) == 0 for tick in ticks)
    assert any(event.kind == "talk_local" for event in ticks[-1].events)
