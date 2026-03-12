from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from llm_social_simulation.simulation.run_open_resources_baseline import run_baseline_experiment


@dataclass
class RunRecord:
    run_id: str
    status: str
    created_at: float
    updated_at: float
    request: dict[str, Any]
    error: str | None = None
    replay: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


@dataclass
class RunStore:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _runs: dict[str, RunRecord] = field(default_factory=dict)

    def create(self, request: dict[str, Any]) -> RunRecord:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = time.time()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            created_at=now,
            updated_at=now,
            request=request,
        )
        with self._lock:
            self._runs[run_id] = record
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def update(self, run_id: str, **kwargs: Any) -> RunRecord | None:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                return None
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = time.time()
            return rec


def _stable_pos(agent_id: int, n_agents: int) -> tuple[float, float]:
    # simple ring around center; kept deterministic for interpretability
    import math

    cx, cy = 10.0, 10.5
    radius = 4.5
    angle = (2.0 * math.pi * agent_id) / max(1, n_agents)
    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius


def _to_replay_payload(
    *,
    run_id: str,
    scenario: str,
    ticks: list[Any],
    summary: dict[str, Any],
    agent_type: str,
) -> dict[str, Any]:
    model_labels = {
        str(agent_id): str(agent_type)
        for agent_id in sorted(int(k) for k in summary.get("final_wealth", {}).keys())
    }
    resource_cap = float(
        summary.get("params", {}).get("config", {}).get("resource_cap")
        or summary.get("params", {}).get("config", {}).get("initial_resource")
        or 100.0
    )

    replay_ticks: list[dict[str, Any]] = []
    for tick in ticks:
        wealth_ids = sorted(int(i) for i in tick.wealth.keys())
        n_agents = max(1, len(wealth_ids))

        agents: list[dict[str, Any]] = []
        for agent_id in wealth_ids:
            x, y = _stable_pos(agent_id=agent_id, n_agents=n_agents)
            reason: str | None = None
            info = getattr(tick, "info", {}) or {}
            last_reasons = info.get("agent_reasons")
            if isinstance(last_reasons, dict):
                r = last_reasons.get(agent_id)
                if isinstance(r, str):
                    reason = r

            agents.append(
                {
                    "id": agent_id,
                    "type": agent_type,
                    "modelLabel": model_labels.get(str(agent_id), agent_type),
                    "x": float(x),
                    "y": float(y),
                    "wealth": float(tick.wealth.get(agent_id, 0.0)),
                    "action": {
                        "harvestRequested": float(tick.harvest_requested.get(agent_id, 0.0)),
                        "harvestActual": float(tick.harvest_actual.get(agent_id, 0.0)),
                        "contribute": float(tick.contribute.get(agent_id, 0.0)),
                        "reward": float(tick.reward.get(agent_id, 0.0)),
                    },
                    "reason": reason,
                    "clamped": {
                        "harvest": bool((tick.clamped.get(agent_id) or {}).get("harvest", False)),
                        "contribute": bool(
                            (tick.clamped.get(agent_id) or {}).get("contribute", False)
                        ),
                    },
                }
            )

        replay_ticks.append(
            {
                "t": int(tick.t),
                "world": {
                    "resource": float(tick.R_after),
                    "resourceCap": float(resource_cap),
                    "pool": float(tick.P_after),
                    "collapsed": bool((tick.info or {}).get("collapsed", False)),
                },
                "agents": agents,
                "metrics": {
                    "totalHarvestRequested": float(sum(tick.harvest_requested.values())),
                    "totalHarvestActual": float(sum(tick.harvest_actual.values())),
                    "totalContribution": float(sum(tick.contribute.values())),
                    "totalReward": float(sum(tick.reward.values())),
                },
            }
        )

    return {
        "meta": {
            "runId": run_id,
            "scenario": scenario,
            "modelLabels": model_labels,
        },
        "ticks": replay_ticks,
    }


def _worker(store: RunStore, run_id: str) -> None:
    rec = store.get(run_id)
    if rec is None:
        return
    request = rec.request

    store.update(run_id, status="running")
    try:
        ticks, summary = run_baseline_experiment(
            agent_type=str(request["agent_type"]),
            n_agents=int(request["n_agents"]),
            rounds=int(request["rounds"]),
            seed=(None if request.get("seed") is None else int(request["seed"])),
            config_overrides=dict(request.get("config_overrides", {})),
            llm_guardrails=bool(request.get("llm_guardrails", True)),
            llm_model=str(request.get("llm_model", "openai/gpt-4o-mini")),
            llm_temperature=float(request.get("llm_temperature", 0.0)),
            llm_max_tokens=int(request.get("llm_max_tokens", 160)),
        )
        replay = _to_replay_payload(
            run_id=run_id,
            scenario="open-resources-baseline",
            ticks=ticks,
            summary=summary,
            agent_type=str(request["agent_type"]),
        )
        llm_diag = summary.get("llm_diagnostics")
        if isinstance(llm_diag, dict):
            replay.setdefault("meta", {})["llmDiagnostics"] = llm_diag

        status = "done"
        error: str | None = None
        if str(request["agent_type"]) == "llm" and isinstance(llm_diag, dict):
            fail_closed = int(llm_diag.get("guardrails_fail_closed_total", 0) or 0)
            llm_calls = int(llm_diag.get("llm_call_total", 0) or 0)
            zero_override = int(llm_diag.get("zero_action_override_total", 0) or 0)
            parsed_zero = int(llm_diag.get("parsed_action_zero_total", 0) or 0)

            if fail_closed > 0 and llm_calls == 0:
                status = "failed"
                error = (
                    "LLM decisions fail-closed in all steps. "
                    "Likely provider/auth/credits/model compatibility issue."
                )
            elif parsed_zero > 0 and zero_override == 0 and fail_closed == 0:
                # Model returned conservative zeros without hard failures.
                error = (
                    "LLM returned zero actions for one or more steps. "
                    "Consider prompt/policy tuning."
                )

        store.update(run_id, status=status, replay=replay, summary=summary, error=error)
    except Exception as exc:  # pragma: no cover
        store.update(run_id, status="failed", error=f"{type(exc).__name__}: {exc}")


class RunAPIHandler(BaseHTTPRequestHandler):
    store: RunStore

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/runs":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        required = {"agent_type", "n_agents", "rounds"}
        missing = [k for k in sorted(required) if k not in payload]
        if missing:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "missing_fields", "fields": missing})
            return

        record = self.store.create(dict(payload))
        threading.Thread(target=_worker, args=(self.store, record.run_id), daemon=True).start()
        self._send(
            HTTPStatus.ACCEPTED,
            {
                "run_id": record.run_id,
                "status": record.status,
                "created_at": record.created_at,
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "runs":
            run_id = parts[2]
            rec = self.store.get(run_id)
            if rec is None:
                self._send(HTTPStatus.NOT_FOUND, {"error": "run_not_found", "run_id": run_id})
                return

            if len(parts) == 3:
                llm_diag: dict[str, Any] | None = None
                if isinstance(rec.summary, dict):
                    raw_diag = rec.summary.get("llm_diagnostics")
                    if isinstance(raw_diag, dict):
                        llm_diag = {
                            "llm_call_total": int(raw_diag.get("llm_call_total", 0) or 0),
                            "parsed_action_zero_total": int(
                                raw_diag.get("parsed_action_zero_total", 0) or 0
                            ),
                            "guardrails_fail_closed_total": int(
                                raw_diag.get("guardrails_fail_closed_total", 0) or 0
                            ),
                            "zero_action_override_total": int(
                                raw_diag.get("zero_action_override_total", 0) or 0
                            ),
                        }
                self._send(
                    HTTPStatus.OK,
                    {
                        "run_id": rec.run_id,
                        "status": rec.status,
                        "error": rec.error,
                        "created_at": rec.created_at,
                        "updated_at": rec.updated_at,
                        "llm_diagnostics": llm_diag,
                    },
                )
                return

            if len(parts) == 4 and parts[3] == "replay":
                if rec.status != "done" or rec.replay is None:
                    self._send(
                        HTTPStatus.CONFLICT,
                        {
                            "error": "replay_not_ready",
                            "run_id": rec.run_id,
                            "status": rec.status,
                            "detail": rec.error,
                        },
                    )
                    return
                self._send(HTTPStatus.OK, rec.replay)
                return

        self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    store = RunStore()

    class BoundHandler(RunAPIHandler):
        pass

    BoundHandler.store = store
    server = ThreadingHTTPServer((host, port), BoundHandler)
    print(f"Open Resources run API listening on http://{host}:{port}")
    server.serve_forever()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API server for Open Resources simulation")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
