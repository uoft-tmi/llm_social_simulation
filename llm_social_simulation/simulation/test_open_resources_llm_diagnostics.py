from llm_social_simulation.simulation.run_open_resources_baseline import _collect_llm_diagnostics


class _DummyPolicy:
    def __init__(self, agent_id: int, llm_call_total: int, parsed_action_zero_total: int):
        self.agent_id = agent_id
        self.llm_call_total = llm_call_total
        self.llm_response_empty_total = 0
        self.parsed_action_zero_total = parsed_action_zero_total
        self.llm_skipped_total = 0
        self.parse_retry_count = 0
        self.filled_id_count = 0
        self.last_raw_output = '{"action":{"harvest":1.0,"contribute":0.0}}'
        self.last_provider = "mock-provider"
        self.client = object()


class _DummyGuardrails:
    def __init__(self, agent_id: int, inner):
        self.agent_id = agent_id
        self.inner = inner
        self.fail_closed_count = 0
        self.harvest_nan_count = 0
        self.contribute_nan_count = 0
        self.harvest_clamp_count = 0
        self.contribute_clamp_count = 0
        self.contribute_clamp_reason_counts = {}
        self.contribute_clamp_events = []
        self.last_error = None


def test_collect_llm_diagnostics_reads_inner_policy_metrics_when_guardrails_enabled() -> None:
    wrapped_agents = [
        _DummyGuardrails(
            agent_id=0,
            inner=_DummyPolicy(0, llm_call_total=5, parsed_action_zero_total=1),
        ),
        _DummyGuardrails(
            agent_id=1,
            inner=_DummyPolicy(1, llm_call_total=5, parsed_action_zero_total=0),
        ),
    ]

    diag = _collect_llm_diagnostics(wrapped_agents, llm_guardrails=True)

    assert diag["llm_call_total"] == 10
    assert diag["parsed_action_zero_total"] == 1
    assert diag["llm_skipped_total"] == 0
    assert diag["per_agent"]["0"]["llm_call_total"] == 5
    assert diag["per_agent"]["1"]["llm_call_total"] == 5
