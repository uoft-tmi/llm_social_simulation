import pytest

from llm_social_simulation.models.parser import parse_open_resources_decision
from llm_social_simulation.models.types import LLMParseError


def test_parse_open_resources_decision_success() -> None:
    content = (
        '{"required":true,"self_id":3,"t":12,'
        '"action":{"harvest":1.1,"contribute":0.3},"reason":"ok"}'
    )

    parsed = parse_open_resources_decision(content, expected_agent_id=3, expected_t=12)
    assert parsed.action.harvest == pytest.approx(1.1)
    assert parsed.action.contribute == pytest.approx(0.3)
    assert parsed.reason == "ok"


def test_parse_open_resources_requires_true_required_field() -> None:
    content = '{"required":false,"self_id":3,"t":12,"action":{"harvest":1.1,"contribute":0.3}}'
    with pytest.raises(LLMParseError):
        parse_open_resources_decision(content, expected_agent_id=3, expected_t=12)


def test_parse_open_resources_rejects_id_or_round_mismatch() -> None:
    content = '{"required":true,"self_id":2,"t":12,"action":{"harvest":1.1,"contribute":0.3}}'
    with pytest.raises(LLMParseError):
        parse_open_resources_decision(content, expected_agent_id=3, expected_t=12)

    content_round = '{"required":true,"self_id":3,"t":11,"action":{"harvest":1.1,"contribute":0.3}}'
    with pytest.raises(LLMParseError):
        parse_open_resources_decision(content_round, expected_agent_id=3, expected_t=12)


def test_parse_open_resources_rejects_negative_values() -> None:
    content = '{"required":true,"self_id":3,"t":12,"action":{"harvest":-1,"contribute":0.3}}'
    with pytest.raises(LLMParseError):
        parse_open_resources_decision(content, expected_agent_id=3, expected_t=12)
