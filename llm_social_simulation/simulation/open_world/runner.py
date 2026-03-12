from __future__ import annotations

import argparse
import json
import random
from typing import Any

from llm_social_simulation.agents.open_world.rule_based import (
    build_deterministic_open_world_agents,
)
from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.open_world.types import OpenWorldTick
from llm_social_simulation.simulation.open_world.world import OpenWorldConfig, OpenWorldGameWorld


def _build_agents(
    *,
    agent_type: str,
    config: OpenWorldConfig,
    llm_guardrails: bool,
    llm_model: str,
    llm_temperature: float,
    llm_max_tokens: int,
    llm_client: LLMClient | None,
) -> list[Any]:
    if agent_type == "rule":
        return build_deterministic_open_world_agents(config.agent_ids)

    if agent_type == "llm":
        from llm_social_simulation.agents.llm.open_world.guardrails import (
            GuardrailsOpenWorldPolicy,
        )
        from llm_social_simulation.agents.llm.open_world.policy import (
            LLMOpenWorldPolicy,
            LLMOpenWorldPolicyConfig,
        )
        from llm_social_simulation.models.openrouter_client import OpenRouterClient

        client = llm_client if llm_client is not None else OpenRouterClient()
        run_id = f"ow_llm_{random.randint(0, 10**9)}"
        raw_policies = [
            LLMOpenWorldPolicy(
                agent_id=agent_id,
                client=client,
                config=LLMOpenWorldPolicyConfig(
                    model=str(llm_model),
                    run_id=run_id,
                    temperature=float(llm_temperature),
                    max_tokens=int(llm_max_tokens),
                ),
            )
            for agent_id in config.agent_ids
        ]
        if not bool(llm_guardrails):
            return raw_policies
        return [
            GuardrailsOpenWorldPolicy(agent_id=policy.agent_id, inner=policy)
            for policy in raw_policies
        ]

    raise ValueError(f"Unsupported agent_type: {agent_type}")


def _collect_llm_diagnostics(agents: list[Any], *, llm_guardrails: bool) -> dict[str, Any]:
    per_agent: dict[str, dict[str, Any]] = {}
    for idx, agent in enumerate(agents):
        policy = getattr(agent, "inner", agent)
        agent_id = str(getattr(policy, "agent_id", getattr(agent, "agent_id", idx)))
        client = getattr(policy, "client", None)
        client_mode = type(client).__name__ if client is not None else "unknown"

        per_agent[agent_id] = {
            "client_mode": client_mode,
            "llm_call_total": int(getattr(policy, "llm_call_total", 0)),
            "llm_response_empty_total": int(getattr(policy, "llm_response_empty_total", 0)),
            "parse_retry_count": int(getattr(policy, "parse_retry_count", 0)),
            "filled_id_count": int(getattr(policy, "filled_id_count", 0)),
            "last_raw_output": getattr(policy, "last_raw_output", None),
            "last_provider": getattr(policy, "last_provider", None),
            "fail_closed_count": int(getattr(agent, "fail_closed_count", 0)),
            "invalid_action_count": int(getattr(agent, "invalid_action_count", 0)),
            "fallback_total": int(getattr(agent, "fallback_total", 0)),
            "last_error": getattr(agent, "last_error", None),
        }

    entries = list(per_agent.values())
    return {
        "guardrails_enabled": bool(llm_guardrails),
        "client_modes": sorted({str(entry["client_mode"]) for entry in entries}),
        "llm_call_total": int(sum(int(entry["llm_call_total"]) for entry in entries)),
        "llm_response_empty_total": int(
            sum(int(entry["llm_response_empty_total"]) for entry in entries)
        ),
        "parse_retry_total": int(sum(int(entry["parse_retry_count"]) for entry in entries)),
        "id_filled_total": int(sum(int(entry["filled_id_count"]) for entry in entries)),
        "guardrails_fail_closed_total": int(
            sum(int(entry["fail_closed_count"]) for entry in entries)
        ),
        "guardrails_invalid_action_total": int(
            sum(int(entry["invalid_action_count"]) for entry in entries)
        ),
        "guardrails_fallback_total": int(sum(int(entry["fallback_total"]) for entry in entries)),
        "per_agent": per_agent,
    }


def run_open_world_baseline(
    *,
    n_agents: int = 4,
    rounds: int = 8,
    seed: int | None = None,
    agent_type: str = "rule",
    llm_guardrails: bool = True,
    llm_model: str = "openai/gpt-4o-mini",
    llm_temperature: float = 0.0,
    llm_max_tokens: int = 220,
    llm_client: LLMClient | None = None,
) -> tuple[list[OpenWorldTick], dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    if n_agents <= 0:
        raise ValueError("n_agents must be > 0")
    if rounds < 0:
        raise ValueError("rounds must be >= 0")
    if agent_type not in {"rule", "llm"}:
        raise ValueError("agent_type must be one of {'rule', 'llm'}")

    config = OpenWorldConfig(agent_ids=tuple(range(int(n_agents))))
    world = OpenWorldGameWorld(config=config)
    agents = _build_agents(
        agent_type=agent_type,
        config=config,
        llm_guardrails=bool(llm_guardrails),
        llm_model=str(llm_model),
        llm_temperature=float(llm_temperature),
        llm_max_tokens=int(llm_max_tokens),
        llm_client=llm_client,
    )

    engine = SimulationEngine(gameworld=world, agents=agents)
    ticks = engine.run(int(rounds))

    final_tick = ticks[-1] if ticks else None
    final_resources = (
        {zone_id: float(location.resource) for zone_id, location in final_tick.locations.items()}
        if final_tick is not None
        else {zone_id: float(location.resource) for zone_id, location in world.locations.items()}
    )
    final_agent_state = (
        {
            str(agent_id): {
                "location_id": state.location_id,
                "energy": float(state.energy),
                "credits": float(state.wealth),
            }
            for agent_id, state in final_tick.agents.items()
        }
        if final_tick is not None
        else {
            str(agent_id): {
                "location_id": state.location_id,
                "energy": float(state.energy),
                "credits": float(state.wealth),
            }
            for agent_id, state in world.agents.items()
        }
    )

    summary = {
        "mode": "open_world",
        "params": {
            "agent_type": str(agent_type),
            "n_agents": int(n_agents),
            "rounds": int(rounds),
            "seed": seed,
            "llm_model": (str(llm_model) if agent_type == "llm" else None),
            "llm_guardrails": bool(llm_guardrails),
        },
        "ticks_executed": len(ticks),
        "final_resources": final_resources,
        "final_agents": final_agent_state,
        "final_total_credits": float(sum(item["credits"] for item in final_agent_state.values())),
        "llm_diagnostics": (
            _collect_llm_diagnostics(agents=agents, llm_guardrails=bool(llm_guardrails))
            if agent_type == "llm"
            else None
        ),
    }
    return ticks, summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run open-world baseline simulation")
    parser.add_argument("--agent-type", choices=["rule", "llm"], default="rule")
    parser.add_argument("--n-agents", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--llm-guardrails", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--llm-model", type=str, default="openai/gpt-4o-mini")
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--llm-max-tokens", type=int, default=220)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _, summary = run_open_world_baseline(
        agent_type=args.agent_type,
        n_agents=args.n_agents,
        rounds=args.rounds,
        seed=args.seed,
        llm_guardrails=args.llm_guardrails,
        llm_model=args.llm_model,
        llm_temperature=args.llm_temperature,
        llm_max_tokens=args.llm_max_tokens,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
