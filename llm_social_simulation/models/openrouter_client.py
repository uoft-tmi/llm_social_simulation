from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib import error
from urllib import request as urlrequest

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency in some test envs
    load_dotenv = None

from .client import LLMClient
from .types import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMRetryableError,
    LLMTimeoutError,
    LLMUsage,
)

if load_dotenv is not None:
    load_dotenv()


class OpenRouterClient(LLMClient):
    """
    Minimal OpenRouter client using OpenAI-compatible Chat Completions endpoint.

    Env vars:
      - OPENROUTER_API_KEY (required if api_key not passed)
      - OPENROUTER_HTTP_REFERER (optional, recommended by OpenRouter)
      - OPENROUTER_X_TITLE (optional, recommended by OpenRouter)
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout_s: float = 30.0,
        base_url: str = "https://openrouter.ai/api/v1",
        http_referer: str | None = None,
        x_title: str | None = None,
    ):
        self.api_key = os.getenv("OPENROUTER_API_KEY") if api_key is None else api_key
        if not self.api_key:
            raise LLMProviderError("OPENROUTER_API_KEY is required for OpenRouterClient")

        self.timeout_s = timeout_s
        self.url = base_url.rstrip("/") + "/chat/completions"

        self.http_referer = http_referer or os.getenv("OPENROUTER_HTTP_REFERER")
        self.x_title = x_title or os.getenv("OPENROUTER_X_TITLE")

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [dict(m) for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format is not None:
            payload["response_format"] = request.response_format

        body = json.dumps(payload).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title

        req = urlrequest.Request(
            self.url,
            data=body,
            method="POST",
            headers=headers,
        )

        try:
            with urlrequest.urlopen(req, timeout=self.timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except TimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except error.HTTPError as exc:
            status = exc.code
            data = exc.read().decode("utf-8", errors="ignore")

            if status in (408, 409, 429, 500, 502, 503, 504):
                if status == 429:
                    raise LLMRateLimitError(data) from exc
                raise LLMRetryableError(data) from exc

            raise LLMProviderError(f"OpenRouter HTTP {status}: {data}") from exc
        except error.URLError as exc:
            raise LLMRetryableError(str(exc)) from exc

        latency_ms = (time.perf_counter() - started) * 1000

        usage_obj = raw.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=usage_obj.get("prompt_tokens"),
            completion_tokens=usage_obj.get("completion_tokens"),
            total_tokens=usage_obj.get("total_tokens"),
        )

        text = self._extract_text(raw)
        raw_meta: dict[str, Any] = {"id": raw.get("id")}
        if isinstance(raw.get("model"), str):
            raw_meta["model"] = raw.get("model")
        if isinstance(raw.get("provider"), dict):
            raw_meta["provider"] = raw.get("provider")

        return LLMResponse(
            content=text,
            model=str(raw.get("model", request.model)),
            request_hash=request.stable_hash(),
            latency_ms=latency_ms,
            usage=usage,
            raw=raw_meta,
        )

    @staticmethod
    def _extract_text(raw: dict[str, Any]) -> str:
        choices = raw.get("choices") or []
        if not choices:
            raise LLMProviderError("OpenRouter response missing choices")

        first = choices[0] or {}
        msg = first.get("message") or {}
        content = msg.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for p in content:
                if isinstance(p, dict):
                    # common patterns: {"type":"text","text":"..."} or {"text":"..."}
                    t = p.get("text")
                    if isinstance(t, str):
                        parts.append(t)
            if parts:
                return "".join(parts)

        # fallback: sometimes "text" exists directly
        if isinstance(first.get("text"), str):
            return first["text"]

        raise LLMProviderError("OpenRouter response did not contain message.content")
