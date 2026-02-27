import pytest
from pydantic import BaseModel

from llm_social_simulation.models.schema import response_format_for_schema, strict_json_parse
from llm_social_simulation.models.types import LLMParseError


class Decision(BaseModel):
    action: str
    confidence: float


class NestedAction(BaseModel):
    harvest: float
    contribute: float


class NestedDecision(BaseModel):
    self_id: int
    action: NestedAction


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


def test_response_format_for_schema_forces_additional_properties_false_recursively() -> None:
    response_format = response_format_for_schema(NestedDecision)
    schema = response_format["json_schema"]["schema"]  # type: ignore[index]
    assert schema["additionalProperties"] is False  # type: ignore[index]

    action_schema = schema["properties"]["action"]  # type: ignore[index]
    if "$ref" in action_schema:
        ref = action_schema["$ref"]  # type: ignore[index]
        ref_name = str(ref).split("/")[-1]
        action_schema = schema["$defs"][ref_name]  # type: ignore[index]
    assert action_schema["additionalProperties"] is False  # type: ignore[index]
