from __future__ import annotations

import json
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any
from urllib import request as urlrequest

from llm_social_simulation.api.run_server import RunAPIHandler, RunStore


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    with urlrequest.urlopen(req, timeout=5.0) as resp:
        raw = resp.read().decode("utf-8")
        body = json.loads(raw)
        return int(resp.status), body


def _wait_for_terminal_status(
    base_url: str,
    run_id: str,
    *,
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        status_code, body = _http_json("GET", f"{base_url}/api/runs/{run_id}")
        assert status_code == 200
        last = body
        if str(body["status"]) in {"done", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not reach terminal state. Last status={last}")


def _start_test_server() -> tuple[ThreadingHTTPServer, str]:
    store = RunStore()

    class BoundHandler(RunAPIHandler):
        pass

    BoundHandler.store = store
    server = ThreadingHTTPServer(("127.0.0.1", 0), BoundHandler)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, base_url


def test_open_world_run_can_be_created_and_replay_retrieved() -> None:
    server, base_url = _start_test_server()
    try:
        status_code, created = _http_json(
            "POST",
            f"{base_url}/api/runs",
            {
                "mode": "open_world",
                "n_agents": 4,
                "rounds": 6,
                "seed": 0,
            },
        )
        assert status_code == 202
        run_id = str(created["run_id"])

        terminal = _wait_for_terminal_status(base_url, run_id)
        assert terminal["status"] == "done"
        assert terminal["mode"] == "open_world"

        replay_code, replay = _http_json("GET", f"{base_url}/api/runs/{run_id}/replay")
        assert replay_code == 200
        assert replay["meta"]["runId"] == run_id
        assert replay["meta"]["scenario"] == "open-world-baseline"
        assert replay["meta"]["mode"] == "open_world"
        assert isinstance(replay["ticks"], list)
        assert len(replay["ticks"]) == 6

        first_tick = replay["ticks"][0]
        assert {"t", "world", "agents", "metrics", "zones", "events", "communications"}.issubset(
            set(first_tick.keys())
        )
        assert len(first_tick["zones"]) == 8
        assert len(first_tick["events"]) >= 4
        assert all("x" in agent and "y" in agent for agent in first_tick["agents"])

        # Ensure replay payload is JSON-serializable end-to-end.
        json.dumps(replay)
    finally:
        server.shutdown()
        server.server_close()


def test_open_resources_default_mode_still_works_via_api() -> None:
    server, base_url = _start_test_server()
    try:
        status_code, created = _http_json(
            "POST",
            f"{base_url}/api/runs",
            {
                "agent_type": "greedy",
                "n_agents": 2,
                "rounds": 3,
                "seed": 0,
                "config_overrides": {
                    "initial_resource": 20.0,
                    "resource_cap": 20.0,
                    "regen_rate": 0.0,
                    "max_harvest_per_step": 5.0,
                },
            },
        )
        assert status_code == 202
        run_id = str(created["run_id"])

        terminal = _wait_for_terminal_status(base_url, run_id)
        assert terminal["status"] == "done"
        assert terminal["mode"] == "open_resources"

        replay_code, replay = _http_json("GET", f"{base_url}/api/runs/{run_id}/replay")
        assert replay_code == 200
        assert replay["meta"]["scenario"] == "open-resources-baseline"
        assert len(replay["ticks"]) == 3
        assert {"t", "world", "agents", "metrics"}.issubset(set(replay["ticks"][0].keys()))
    finally:
        server.shutdown()
        server.server_close()
