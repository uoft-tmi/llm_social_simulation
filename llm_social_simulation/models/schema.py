from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .types import LLMParseError

TModel = TypeVar("TModel", bound=BaseModel)


def _strip_markdown_fences(content: str) -> str:
    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 2:
        return text

    # --- drop opening fence (with optional language tag) and trailing fence ---
    body = lines[1:]
    if body and body[-1].strip().startswith("```"):
        body = body[:-1]
    return "\n".join(body).strip()


def _extract_likely_json_object(content: str) -> str:
    text = _strip_markdown_fences(content)
    if not text:
        return text

    # --- fast path: already JSON object text ---
    if text.startswith("{") and text.endswith("}"):
        return text

    # --- try to capture a fenced/embedded JSON object block ---
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0).strip()
    return text


def strict_json_parse(content: str, schema: type[TModel]) -> TModel:
    """Parse JSON text into a pydantic schema with strict validation."""
    try:
        payload = json.loads(_extract_likely_json_object(content))
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"Invalid JSON response: {exc}") from exc

    try:
        return schema.model_validate(payload, strict=True)
    except ValidationError as exc:
        raise LLMParseError(f"Schema validation failed: {exc}") from exc


def response_format_for_schema(schema: type[BaseModel]) -> dict[str, object]:
    """Provider-ready json-schema response format."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": schema.model_json_schema(),
            "strict": True,
        },
    }
