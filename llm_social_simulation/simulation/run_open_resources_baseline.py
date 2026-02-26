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


def _build_agents(agent_type: str, config: OpenResourcesConfig):
    max_h = float(config.max_harvest_per_step)
    cap = (
        float(config.resource_cap)
        if config.resource_cap is not None
        else max(float(config.initial_resource), 1.0)
    )

    if agent_type == "greedy":
        return [
            GreedyHarvesterAgent(agent_id=agent_id, max_harvest_per_step=max_h)
            for agent_id in config.agent_ids
        ]
    if agent_type == "coop":
        return [
            CooperativeSustainableAgent(agent_id=agent_id, max_harvest_per_step=max_h)
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
                    CooperativeSustainableAgent(agent_id=agent_id, max_harvest_per_step=max_h)
                )
        return agents

    raise ValueError(f"Unsupported agent_type: {agent_type}")


def run_baseline_experiment(
    *,
    agent_type: str,
    n_agents: int,
    rounds: int,
    seed: int | None,
    config_overrides: dict[str, float | str | None] | None = None,
) -> tuple[list[OpenResourcesTick], dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    overrides = dict(config_overrides or {})
    agent_ids = tuple(range(n_agents))

    config = OpenResourcesConfig(agent_ids=agent_ids, **overrides)
    world = OpenResourcesGameWorld(config=config)
    agents = _build_agents(agent_type=agent_type, config=config)

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
    }
    return ticks, summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Open Resources baseline experiments.")
    parser.add_argument(
        "--agent-type", choices=["greedy", "coop", "adaptive", "mixed"], required=True
    )
    parser.add_argument("--n-agents", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--initial-resource", type=float, default=100.0)
    parser.add_argument("--resource-cap", type=float, default=None)
    parser.add_argument("--regen-rate", type=float, default=0.05)
    parser.add_argument("--regen-mode", choices=["logistic", "linear"], default="logistic")
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
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
