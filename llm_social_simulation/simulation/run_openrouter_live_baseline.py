from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import dataclass
from typing import Any

from llm_social_simulation.models.client import LLMClient
from llm_social_simulation.models.openrouter_client import OpenRouterClient
from llm_social_simulation.models.policies.llm_open_resources import (
    LLMOpenResourcesPolicy,
    LLMOpenResourcesPolicyConfig,
)
from llm_social_simulation.models.types import LLMProviderError, LLMRequest, LLMResponse
from llm_social_simulation.simulation.agents_model_based import LLMOpenResourcesAgent
from llm_social_simulation.simulation.analytics import (
    collapse_time,
    gini_final_wealth,
    pool_series,
    resource_series,
)
from llm_social_simulation.simulation.gameworld import (
    OpenResourcesConfig,
    OpenResourcesGameWorld,
    OpenResourcesTick,
)


def _parse_models(raw: str) -> list[str]:
    return [model.strip() for model in raw.split(",") if model.strip()]


def _default_models() -> list[str]:
    return _parse_models(
        os.getenv(
            "OPENROUTER_TEST_MODELS",
            "openai/gpt-4o-mini,google/gemini-2.0-flash-001",
        )
    )


def _is_schema_unsupported_provider_error(message: str) -> bool:
    return (
        "response_format" in message
        or "Invalid schema" in message
        or "additionalProperties" in message
    )


def _fmt(value: float) -> str:
    return f"{value:.3f}"


@dataclass
class ModelRunFailedError(Exception):
    """Wrap a model-run failure with a partial summary for usage/accounting."""

    cause: Exception
    summary: dict[str, Any]

    def __str__(self) -> str:
        return str(self.cause)


class GameStatusOpenRouterClient(LLMClient):
    """OpenRouter wrapper that prints concise decision logs instead of full prompts."""

    def __init__(self, inner: OpenRouterClient, *, show_llm_log: bool):
        self.inner = inner
        self.show_llm_log = show_llm_log
        self._request_count = 0
        self._response_count = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0
        self._latency_ms_total = 0.0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self._request_count += 1
        if self.show_llm_log:
            self._print_request_summary(request)

        response = self.inner.generate(request)
        self._response_count += 1
        self._latency_ms_total += float(response.latency_ms)
        if response.usage is not None:
            self._prompt_tokens += int(response.usage.prompt_tokens or 0)
            self._completion_tokens += int(response.usage.completion_tokens or 0)
            self._total_tokens += int(response.usage.total_tokens or 0)

        if self.show_llm_log:
            self._print_response_summary(response)
        return response

    def _print_request_summary(self, request: LLMRequest) -> None:
        #  agent_id = request.metadata.get("agent_id", "?")
        #  round_idx = request.metadata.get("t", "?")
        r_value = "?"
        p_value = "?"
        wealth = "?"
        mem_len = "?"

        try:
            payload = json.loads(request.messages[1]["content"])
            obs = payload.get("observation", {})
            r_value = _fmt(float(obs.get("R", 0.0)))
            p_value = _fmt(float(obs.get("P", 0.0)))
            wealth = _fmt(float(obs.get("self_wealth", 0.0)))
            mem_len = len(payload.get("memory_window", []))
        except Exception:
            pass
        print(
            "[req] ",
            # "model={request.model} t={round_idx} agent={agent_id} "
            f"R={r_value} P={p_value} wealth={wealth} mem={mem_len}",
            flush=True,
        )

    def _print_response_summary(self, response: LLMResponse) -> None:
        action_summary = "unparsed"
        reason_summary = ""
        try:
            payload = self._extract_payload_for_log(response.content)
            action = payload.get("action", {})
            harvest = float(action.get("harvest", 0.0))
            contribute = float(action.get("contribute", 0.0))
            action_summary = f"harvest={harvest:.3f} contribute={contribute:.3f}"
            reason = payload.get("reason")
            if isinstance(reason, str) and reason.strip():
                clean_reason = " ".join(reason.strip().split())
                if len(clean_reason) > 140:
                    clean_reason = clean_reason[:137] + "..."
                reason_summary = f' reason="{clean_reason}"'
            elif reason is None:
                reason_summary = " reason=null"
        except Exception:
            action_summary = "invalid_json"
            reason_summary = " reason=unavailable"

        #  total_tokens = response.usage.total_tokens if response.usage is not None else None
        #  token_text = f" total_tokens={total_tokens}" if total_tokens is not None else ""
        print(
            "[res] ",
            # "model={response.model} ",
            f"{action_summary}{reason_summary}",
            # f"latency_ms={response.latency_ms:.1f}{token_text}",
            flush=True,
        )

    @staticmethod
    def _extract_payload_for_log(content: str) -> dict[str, Any]:
        text = content.strip()
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

        # --- recover when providers wrap JSON in markdown or extra text ---
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2:
                body = lines[1:]
                if body and body[-1].strip().startswith("```"):
                    body = body[:-1]
                text = "\n".join(body).strip()

        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("no_json_object_found")

        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("json_payload_not_object")
        return payload

    def usage_summary(self) -> dict[str, Any]:
        avg_latency_ms = (
            self._latency_ms_total / self._response_count if self._response_count > 0 else 0.0
        )
        return {
            "request_count": self._request_count,
            "response_count": self._response_count,
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": round(avg_latency_ms, 2),
            "latency_ms_total": round(self._latency_ms_total, 2),
        }


def _build_llm_agents(
    *,
    model: str,
    n_agents: int,
    client: LLMClient,
    run_id: str,
    temperature: float,
    max_tokens: int,
) -> list[LLMOpenResourcesAgent]:
    agents: list[LLMOpenResourcesAgent] = []
    for agent_id in range(n_agents):
        policy = LLMOpenResourcesPolicy(
            agent_id=agent_id,
            client=client,
            config=LLMOpenResourcesPolicyConfig(
                model=model,
                run_id=run_id,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
        )
        agents.append(LLMOpenResourcesAgent(agent_id=agent_id, policy=policy))
    return agents


def _run_with_round_logging(
    *,
    world: OpenResourcesGameWorld,
    agents: list[LLMOpenResourcesAgent],
    rounds: int,
    show_round_log: bool,
) -> tuple[list[OpenResourcesTick], bool, Exception | None]:
    ticks: list[OpenResourcesTick] = []
    interrupted = False
    error: Exception | None = None

    try:
        for _ in range(rounds):
            actions: dict[int, Any] = {}
            for agent in agents:
                obs = world.get_observation(agent.agent_id)
                actions[agent.agent_id] = agent.decide(obs)

            tick = world.apply_actions(actions)
            ticks.append(tick)

            if show_round_log:
                total_requested = sum(tick.harvest_requested.values())
                total_actual = sum(tick.harvest_actual.values())
                total_contrib = sum(tick.contribute.values())
                print(
                    f"[round {tick.t:03d}] "
                    f"R {_fmt(tick.R_before)}->{_fmt(tick.R_after)} "
                    f"P {_fmt(tick.P_before)}->{_fmt(tick.P_after)} "
                    f"H_req={_fmt(total_requested)} H_act={_fmt(total_actual)} "
                    f"C={_fmt(total_contrib)} collapsed={tick.info.get('collapsed', False)}",
                    flush=True,
                )
    except KeyboardInterrupt:
        interrupted = True
        print("\n[run] Interrupted by user; returning partial results.", flush=True)
    except Exception as exc:  # pragma: no cover
        error = exc

    return ticks, interrupted, error


def _build_run_summary(
    *,
    model: str,
    n_agents: int,
    rounds: int,
    seed: int | None,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    config: OpenResourcesConfig,
    ticks: list[OpenResourcesTick],
    usage: dict[str, Any],
    terminated_early: bool,
) -> dict[str, Any]:
    agent_ids = tuple(range(n_agents))
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

    return {
        "model": model,
        "terminated_early": terminated_early,
        "collapsed": ct is not None,
        "collapse_time": ct,
        "final_R": final_r,
        "final_P": final_p,
        "final_wealth": final_wealth,
        "gini_final": float(gini_final_wealth(ticks)),
        "usage": usage,
        "params": {
            "n_agents": n_agents,
            "rounds": rounds,
            "seed": seed,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout_s": timeout_s,
            "config": config.__dict__,
        },
        "R_series_head": resource_series(ticks)[:10],
        "P_series_head": pool_series(ticks)[:10],
    }


def run_live_openrouter_experiment(
    *,
    model: str,
    n_agents: int,
    rounds: int,
    seed: int | None,
    config_overrides: dict[str, float | str | None] | None = None,
    timeout_s: float = 60.0,
    temperature: float = 0.0,
    max_tokens: int = 220,
    show_llm_log: bool = True,
    show_round_log: bool = True,
) -> tuple[list[OpenResourcesTick], dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    overrides = dict(config_overrides or {})
    agent_ids = tuple(range(n_agents))

    config = OpenResourcesConfig(agent_ids=agent_ids, **overrides)
    world = OpenResourcesGameWorld(config=config)
    raw_client = OpenRouterClient(timeout_s=timeout_s)
    client = GameStatusOpenRouterClient(raw_client, show_llm_log=show_llm_log)

    run_id = f"live-openrouter-{model.replace('/', '-')[:40]}"
    agents = _build_llm_agents(
        model=model,
        n_agents=n_agents,
        client=client,
        run_id=run_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    ticks, interrupted, error = _run_with_round_logging(
        world=world,
        agents=agents,
        rounds=rounds,
        show_round_log=show_round_log,
    )

    usage = client.usage_summary()
    summary = _build_run_summary(
        model=model,
        n_agents=n_agents,
        rounds=rounds,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        config=config,
        ticks=ticks,
        usage=usage,
        terminated_early=interrupted,
    )
    if error is not None:
        raise ModelRunFailedError(cause=error, summary=summary)

    return ticks, summary


def run_live_openrouter_suite(
    *,
    models: list[str],
    n_agents: int,
    rounds: int,
    seed: int | None,
    config_overrides: dict[str, float | str | None],
    timeout_s: float,
    temperature: float,
    max_tokens: int,
    show_llm_log: bool,
    show_round_log: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for model in models:
        print(f"\n=== MODEL {model} ===", flush=True)
        try:
            _, summary = run_live_openrouter_experiment(
                model=model,
                n_agents=n_agents,
                rounds=rounds,
                seed=seed,
                config_overrides=config_overrides,
                timeout_s=timeout_s,
                temperature=temperature,
                max_tokens=max_tokens,
                show_llm_log=show_llm_log,
                show_round_log=show_round_log,
            )
            status = "aborted" if summary.get("terminated_early") else "passed"
            results.append({"model": model, "status": status, "summary": summary})
            if status == "aborted":
                break
        except ModelRunFailedError as exc:
            msg = str(exc.cause)
            if isinstance(exc.cause, LLMProviderError):
                if "OPENROUTER_API_KEY is required" in msg:
                    results.append(
                        {
                            "model": model,
                            "status": "skipped",
                            "reason": "missing_api_key",
                            "error": msg,
                            "summary": exc.summary,
                        }
                    )
                elif _is_schema_unsupported_provider_error(msg):
                    results.append(
                        {
                            "model": model,
                            "status": "skipped",
                            "reason": "unsupported_response_format",
                            "error": msg,
                            "summary": exc.summary,
                        }
                    )
                else:
                    results.append(
                        {
                            "model": model,
                            "status": "failed",
                            "reason": "provider_error",
                            "error": msg,
                            "summary": exc.summary,
                        }
                    )
            else:
                results.append(
                    {
                        "model": model,
                        "status": "failed",
                        "reason": "exception",
                        "error": msg,
                        "summary": exc.summary,
                    }
                )
        except LLMProviderError as exc:
            msg = str(exc)
            if "OPENROUTER_API_KEY is required" in msg:
                results.append(
                    {
                        "model": model,
                        "status": "skipped",
                        "reason": "missing_api_key",
                        "error": msg,
                    }
                )
            elif _is_schema_unsupported_provider_error(msg):
                results.append(
                    {
                        "model": model,
                        "status": "skipped",
                        "reason": "unsupported_response_format",
                        "error": msg,
                    }
                )
            else:
                results.append(
                    {
                        "model": model,
                        "status": "failed",
                        "reason": "provider_error",
                        "error": msg,
                    }
                )
        except Exception as exc:  # pragma: no cover
            results.append(
                {
                    "model": model,
                    "status": "failed",
                    "reason": "exception",
                    "error": str(exc),
                }
            )
        except KeyboardInterrupt:  # pragma: no cover
            results.append(
                {
                    "model": model,
                    "status": "aborted",
                    "reason": "keyboard_interrupt",
                    "error": "Interrupted by user",
                }
            )
            break

    usage_totals = {
        "request_count": 0,
        "response_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms_total": 0.0,
    }
    for item in results:
        summary = item.get("summary")
        if not isinstance(summary, dict):
            continue
        usage = summary.get("usage")
        if isinstance(usage, dict):
            usage_totals["request_count"] += int(usage.get("request_count") or 0)
            usage_totals["response_count"] += int(usage.get("response_count") or 0)
            usage_totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            usage_totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            usage_totals["total_tokens"] += int(usage.get("total_tokens") or 0)
            usage_totals["latency_ms_total"] += float(usage.get("latency_ms_total") or 0.0)

    usage_totals["latency_ms_total"] = round(float(usage_totals["latency_ms_total"]), 2)
    return {
        "results": results,
        "counts": {
            "passed": sum(1 for r in results if r["status"] == "passed"),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "aborted": sum(1 for r in results if r["status"] == "aborted"),
        },
        "usage_totals": usage_totals,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run live OpenRouter OpenResources experiments with baseline-style parameters."
        )
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(_default_models()),
        help="Comma-separated model list. Example: openai/gpt-4o-mini,google/gemini-2.0-flash-001",
    )
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
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=float(os.getenv("OPENROUTER_TEST_TIMEOUT_S", "60")),
    )
    parser.add_argument(
        "--quiet-llm-log",
        action="store_true",
        help="Hide per-decision LLM request/response summaries.",
    )
    parser.add_argument(
        "--quiet-game-log",
        action="store_true",
        help="Hide per-round game status summaries.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    models = _parse_models(args.models)
    if not models:
        raise SystemExit("No models provided. Pass --models with at least one model id.")

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

    suite = run_live_openrouter_suite(
        models=models,
        n_agents=args.n_agents,
        rounds=args.rounds,
        seed=args.seed,
        config_overrides=overrides,
        timeout_s=args.timeout_s,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        show_llm_log=not args.quiet_llm_log,
        show_round_log=not args.quiet_game_log,
    )
    print("\n=== RUN SUMMARY ===")
    print(json.dumps(suite, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""
uv run python -m llm_social_simulation.simulation.run_openrouter_live_baseline \
  --models "google/gemini-2.5-flash-lite,\
deepseek/deepseek-v3.2,\
  --n-agents 6 --rounds 80 --seed 0 \
  --initial-resource 30 --resource-cap 60 \
  --regen-rate 0.1 --regen-mode logistic \
  --contribution-regen-weight 0.5 \
  --max-harvest-per-step 10 \
  --initial-wealth 10 --initial-pool 0 \
  --governance-reward-rate 0.0 --reward-mode proportional \
  --collapse-threshold 0.5
"""
