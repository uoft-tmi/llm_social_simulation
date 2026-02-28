from __future__ import annotations

import argparse
import json
import random
from typing import Any

from llm_social_simulation.simulation.agents_rule_based import (
    CooperativeSustainableAgent,
    GreedyHarvesterAgent,
    ResourceAwareAdaptiveAgent,
)
from llm_social_simulation.simulation.analytics import (
    collapse_time,
    gini_final_wealth,
    pool_series,
    resource_series,
)
from llm_social_simulation.simulation.engine import SimulationEngine
from llm_social_simulation.simulation.gameworld import (
    OpenResourcesConfig,
    OpenResourcesGameWorld,
    OpenResourcesTick,
)


def _build_agents(
    agent_type: str,
    config: OpenResourcesConfig,
    *,
    llm_guardrails: bool = True,
    llm_model: str = "openai/gpt-4o-mini",
    llm_temperature: float = 0.0,
    llm_max_tokens: int = 160,
):
    max_h = float(config.max_harvest_per_step)
    cap = (
        float(config.resource_cap)
        if config.resource_cap is not None
        else max(float(config.initial_resource), 1.0)
    )
    r = float(config.regen_rate)
    regen_mode = str(config.regen_mode)

    if agent_type == "greedy":
        return [
            GreedyHarvesterAgent(agent_id=agent_id, max_harvest_per_step=max_h)
            for agent_id in config.agent_ids
        ]
    if agent_type == "coop":
        return [
            CooperativeSustainableAgent(
                agent_id=agent_id,
                max_harvest_per_step=max_h,
                resource_cap=cap,
                regen_rate=r,
                regen_mode=regen_mode,
                safety=0.8,
                contrib_rate=0.02,
                min_resource_frac=0.05,
            )
            for agent_id in config.agent_ids
        ]
    if agent_type == "adaptive":
        return [
            ResourceAwareAdaptiveAgent(
                agent_id=agent_id,
                max_harvest_per_step=max_h,
                resource_cap=cap,
            )
            for agent_id in config.agent_ids
        ]
    if agent_type == "mixed":
        half = len(config.agent_ids) // 2
        agents = []
        for idx, agent_id in enumerate(config.agent_ids):
            if idx < half:
                agents.append(GreedyHarvesterAgent(agent_id=agent_id, max_harvest_per_step=max_h))
            else:
                agents.append(
                    CooperativeSustainableAgent(
                        agent_id=agent_id,
                        max_harvest_per_step=max_h,
                        resource_cap=cap,
                        regen_rate=r,
                        regen_mode=regen_mode,
                        safety=0.8,
                        contrib_rate=0.02,
                        min_resource_frac=0.05,
                    )
                )
        return agents

    if agent_type == "llm":
        from llm_social_simulation.models.openrouter_client import OpenRouterClient
        from llm_social_simulation.models.policies.guardrails import GuardrailsPolicy
        from llm_social_simulation.models.policies.llm_open_resources import (
            LLMOpenResourcesPolicy,
            LLMOpenResourcesPolicyConfig,
        )

        client = OpenRouterClient()
        run_id = f"or_llm_{random.randint(0, 10**9)}"
        raw_policies = [
            LLMOpenResourcesPolicy(
                agent_id=agent_id,
                client=client,
                config=LLMOpenResourcesPolicyConfig(
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
            GuardrailsPolicy(
                agent_id=policy.agent_id,
                inner=policy,
                max_harvest_per_step=max_h,
            )
            for policy in raw_policies
        ]

    raise ValueError(f"Unsupported agent_type: {agent_type}")


def _collect_llm_diagnostics(agents: list[Any], llm_guardrails: bool) -> dict[str, Any]:
    per_agent: dict[str, dict[str, Any]] = {}
    for idx, agent in enumerate(agents):
        # When guardrails are enabled, policy metrics live on wrapper.inner.
        policy = getattr(agent, "inner", agent)
        agent_id = str(getattr(policy, "agent_id", getattr(agent, "agent_id", idx)))

        client = getattr(policy, "client", None)
        client_mode = type(client).__name__ if client is not None else "unknown"

        per_agent[agent_id] = {
            "client_mode": client_mode,
            "llm_call_total": int(getattr(policy, "llm_call_total", 0)),
            "llm_response_empty_total": int(getattr(policy, "llm_response_empty_total", 0)),
            "parsed_action_zero_total": int(getattr(policy, "parsed_action_zero_total", 0)),
            "llm_skipped_total": int(getattr(policy, "llm_skipped_total", 0)),
            "parse_retry_count": int(getattr(policy, "parse_retry_count", 0)),
            "filled_id_count": int(getattr(policy, "filled_id_count", 0)),
            "fail_closed_count": int(getattr(agent, "fail_closed_count", 0)),
            "harvest_nan_count": int(getattr(agent, "harvest_nan_count", 0)),
            "contribute_nan_count": int(getattr(agent, "contribute_nan_count", 0)),
            "harvest_clamp_count": int(getattr(agent, "harvest_clamp_count", 0)),
            "contribute_clamp_count": int(getattr(agent, "contribute_clamp_count", 0)),
            "contribute_clamp_reason_counts": dict(
                getattr(agent, "contribute_clamp_reason_counts", {})
            ),
            "last_contribute_clamp_event": (
                getattr(agent, "contribute_clamp_events", [])[-1]
                if getattr(agent, "contribute_clamp_events", [])
                else None
            ),
            "last_raw_output": getattr(policy, "last_raw_output", None),
            "last_provider": getattr(policy, "last_provider", None),
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
        "parsed_action_zero_total": int(
            sum(int(entry["parsed_action_zero_total"]) for entry in entries)
        ),
        "llm_skipped_total": int(sum(int(entry["llm_skipped_total"]) for entry in entries)),
        "parse_retry_total": int(sum(int(entry["parse_retry_count"]) for entry in entries)),
        "id_filled_total": int(sum(int(entry["filled_id_count"]) for entry in entries)),
        "guardrails_fail_closed_total": int(
            sum(int(entry["fail_closed_count"]) for entry in entries)
        ),
        "guardrails_harvest_clamp_total": int(
            sum(int(entry["harvest_clamp_count"]) for entry in entries)
        ),
        "guardrails_contribute_clamp_total": int(
            sum(int(entry["contribute_clamp_count"]) for entry in entries)
        ),
        "guardrails_contribute_clamp_reason_totals": {
            "nan": int(
                sum(int(entry["contribute_clamp_reason_counts"].get("nan", 0)) for entry in entries)
            ),
            "negative": int(
                sum(
                    int(entry["contribute_clamp_reason_counts"].get("negative", 0))
                    for entry in entries
                )
            ),
            "above_max_contribute": int(
                sum(
                    int(entry["contribute_clamp_reason_counts"].get("above_max_contribute", 0))
                    for entry in entries
                )
            ),
        },
        "per_agent": per_agent,
    }


def run_baseline_experiment(
    *,
    agent_type: str,
    n_agents: int,
    rounds: int,
    seed: int | None,
    config_overrides: dict[str, float | str | None] | None = None,
    llm_guardrails: bool = True,
    llm_model: str = "openai/gpt-4o-mini",
    llm_temperature: float = 0.0,
    llm_max_tokens: int = 160,
) -> tuple[list[OpenResourcesTick], dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    overrides = dict(config_overrides or {})
    agent_ids = tuple(range(n_agents))

    config = OpenResourcesConfig(agent_ids=agent_ids, **overrides)
    world = OpenResourcesGameWorld(config=config)
    agents = _build_agents(
        agent_type=agent_type,
        config=config,
        llm_guardrails=llm_guardrails,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
    )

    engine = SimulationEngine(world, agents)
    ticks = engine.run(rounds)

    final_tick = ticks[-1] if ticks else None
    final_wealth = (
        dict(final_tick.wealth)
        if final_tick is not None
        else {i: config.initial_wealth for i in agent_ids}
    )
    final_r = (
        float(final_tick.R_after) if final_tick is not None else float(config.initial_resource)
    )
    final_p = float(final_tick.P_after) if final_tick is not None else float(config.initial_pool)

    ct = collapse_time(ticks)
    llm_diagnostics: dict[str, Any] | None = None
    if agent_type == "llm":
        llm_diagnostics = _collect_llm_diagnostics(agents=agents, llm_guardrails=llm_guardrails)

    summary = {
        "collapsed": ct is not None,
        "collapse_time": ct,
        "final_R": final_r,
        "final_P": final_p,
        "final_wealth": final_wealth,
        "gini_final": float(gini_final_wealth(ticks)),
        "params": {
            "agent_type": agent_type,
            "n_agents": n_agents,
            "rounds": rounds,
            "seed": seed,
            "config": config.__dict__,
        },
        "R_series_head": resource_series(ticks)[:10],
        "P_series_head": pool_series(ticks)[:10],
        "llm_diagnostics": llm_diagnostics,
    }
    return ticks, summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Open Resources baseline experiments.")
    parser.add_argument(
        "--agent-type", choices=["greedy", "coop", "adaptive", "mixed", "llm"], required=True
    )
    parser.add_argument(
        "--llm-guardrails",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable safety clamps around LLM actions (recommended).",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="openai/gpt-4o-mini",
        help="OpenRouter model string when agent-type=llm",
    )
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--llm-max-tokens", type=int, default=160)
    parser.add_argument("--n-agents", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--initial-resource", type=float, default=100.0)
    parser.add_argument("--resource-cap", type=float, default=None)
    parser.add_argument("--regen-rate", type=float, default=0.05)
    parser.add_argument("--regen-mode", choices=["logistic", "linear"], default="logistic")
    parser.add_argument("--contribution-regen-weight", type=float, default=0.0)
    parser.add_argument("--max-harvest-per-step", type=float, default=1_000_000.0)
    parser.add_argument("--initial-wealth", type=float, default=0.0)
    parser.add_argument("--initial-pool", type=float, default=0.0)
    parser.add_argument("--governance-reward-rate", type=float, default=0.0)
    parser.add_argument("--reward-mode", choices=["proportional", "equal"], default="proportional")
    parser.add_argument("--collapse-threshold", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    overrides: dict[str, float | str | None] = {
        "initial_resource": args.initial_resource,
        "resource_cap": args.resource_cap,
        "regen_rate": args.regen_rate,
        "regen_mode": args.regen_mode,
        "contribution_regen_weight": args.contribution_regen_weight,
        "max_harvest_per_step": args.max_harvest_per_step,
        "initial_wealth": args.initial_wealth,
        "initial_pool": args.initial_pool,
        "governance_reward_rate": args.governance_reward_rate,
        "reward_mode": args.reward_mode,
        "collapse_threshold": args.collapse_threshold,
    }
    _, summary = run_baseline_experiment(
        agent_type=args.agent_type,
        n_agents=args.n_agents,
        rounds=args.rounds,
        seed=args.seed,
        config_overrides=overrides,
        llm_guardrails=args.llm_guardrails,
        llm_model=args.llm_model,
        llm_temperature=args.llm_temperature,
        llm_max_tokens=args.llm_max_tokens,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""
uv run python -m llm_social_simulation.simulation.run_open_resources_baseline \
  --agent-type coop --n-agents 6 --rounds 80 --seed 0 \
  --initial-resource 30 --resource-cap 60 \
  --regen-rate 0.1 --regen-mode logistic \
  --max-harvest-per-step 10 \
  --initial-wealth 10 --governance-reward-rate 0.0 \
  --collapse-threshold 0.5
"""
