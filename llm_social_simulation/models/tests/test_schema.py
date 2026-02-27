import pytest
from pydantic import BaseModel

from llm_social_simulation.models.schema import strict_json_parse
from llm_social_simulation.models.types import LLMParseError


class Decision(BaseModel):
    action: str
    confidence: float


def test_strict_json_parse_success() -> None:
    parsed = strict_json_parse('{"action":"C","confidence":0.5}', Decision)
    assert parsed.action == "C"


def test_strict_json_parse_rejects_non_json() -> None:
    with pytest.raises(LLMParseError):
        strict_json_parse("action=C", Decision)


def test_strict_json_parse_rejects_schema_mismatch() -> None:
    with pytest.raises(LLMParseError):
        strict_json_parse('{"action":"C","confidence":"0.5"}', Decision)


def test_strict_json_parse_accepts_markdown_fenced_json() -> None:
    content = '```json\n{"action":"C","confidence":0.7}\n```'
    parsed = strict_json_parse(content, Decision)
    assert parsed.action == "C"
    assert parsed.confidence == pytest.approx(0.7)


def test_strict_json_parse_accepts_json_embedded_in_text() -> None:
    content = 'Here is my output: {"action":"D","confidence":0.2} Thanks.'
    parsed = strict_json_parse(content, Decision)
    assert parsed.action == "D"
    assert parsed.confidence == pytest.approx(0.2)
