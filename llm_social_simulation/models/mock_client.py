from __future__ import annotations

import json
import time
from hashlib import sha256

from .client import LLMClient
from .types import LLMRequest, LLMResponse


class MockClient(LLMClient):
    """Deterministic mock provider for tests and local simulation."""

    def __init__(self, fixed_latency_ms: float = 1.0, fixed_content: str | None = None):
        self.fixed_latency_ms = fixed_latency_ms
        self.fixed_content = fixed_content

    def generate(self, request: LLMRequest) -> LLMResponse:
        request_hash = request.stable_hash()
        if self.fixed_content is not None:
            content = str(self.fixed_content)
        else:
            seed_payload = {
                "hash": request_hash,
                "model": request.model,
            }
            digest = sha256(json.dumps(seed_payload, sort_keys=True).encode("utf-8")).hexdigest()[
                :16
            ]
            content = json.dumps({"mock_id": digest, "decision": "C"}, sort_keys=True)
        time.sleep(self.fixed_latency_ms / 1000.0)
        return LLMResponse(
            content=content,
            model=f"mock:{request.model}",
            request_hash=request_hash,
            latency_ms=self.fixed_latency_ms,
            usage=None,
            raw={"source": "mock"},
        )
