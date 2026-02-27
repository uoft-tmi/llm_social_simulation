from llm_social_simulation.models.types import LLMProviderError
from llm_social_simulation.simulation import run_openrouter_live_baseline as live_runner


def _suite_kwargs() -> dict[str, object]:
    return {
        "models": ["unit-model"],
        "n_agents": 1,
        "rounds": 2,
        "seed": 0,
        "config_overrides": {},
        "timeout_s": 1.0,
        "temperature": 0.0,
        "max_tokens": 32,
        "show_llm_log": False,
        "show_round_log": False,
    }


def test_suite_usage_totals_include_failed_model_with_partial_summary(monkeypatch) -> None:
    summary = {
        "terminated_early": False,
        "usage": {
            "request_count": 3,
            "response_count": 2,
            "prompt_tokens": 100,
            "completion_tokens": 30,
            "total_tokens": 130,
            "latency_ms_total": 55.5,
        },
    }

    def _raise_failed(**kwargs):  # noqa: ANN001
        del kwargs
        raise live_runner.ModelRunFailedError(
            cause=Exception("bad json"),
            summary=summary,
        )

    monkeypatch.setattr(live_runner, "run_live_openrouter_experiment", _raise_failed)
    suite = live_runner.run_live_openrouter_suite(**_suite_kwargs())

    assert suite["counts"]["failed"] == 1
    assert suite["usage_totals"]["request_count"] == 3
    assert suite["usage_totals"]["total_tokens"] == 130
    assert suite["usage_totals"]["latency_ms_total"] == 55.5


def test_suite_usage_totals_include_skipped_provider_model_summary(monkeypatch) -> None:
    summary = {
        "terminated_early": False,
        "usage": {
            "request_count": 1,
            "response_count": 0,
            "prompt_tokens": 40,
            "completion_tokens": 0,
            "total_tokens": 40,
            "latency_ms_total": 10.0,
        },
    }

    def _raise_skipped(**kwargs):  # noqa: ANN001
        del kwargs
        raise live_runner.ModelRunFailedError(
            cause=LLMProviderError("Invalid schema ... additionalProperties ..."),
            summary=summary,
        )

    monkeypatch.setattr(live_runner, "run_live_openrouter_experiment", _raise_skipped)
    suite = live_runner.run_live_openrouter_suite(**_suite_kwargs())

    assert suite["counts"]["skipped"] == 1
    assert suite["usage_totals"]["request_count"] == 1
    assert suite["usage_totals"]["total_tokens"] == 40
