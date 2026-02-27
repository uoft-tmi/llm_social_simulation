from llm_social_simulation.models.memory import MemoryEvent, MemoryWindowStore


def _event(t: int, reason: str | None = None) -> MemoryEvent:
    return MemoryEvent(
        t=t,
        R=100.0 - t,
        P=float(t),
        self_wealth=10.0 + t,
        action={"harvest": 1.0 + t / 10.0, "contribute": t / 20.0},
        reason=reason,
    )


def test_memory_window_caps_round_count() -> None:
    store = MemoryWindowStore(max_rounds=3, max_prompt_memory_tokens=10_000)
    for t in range(6):
        store.append(1, _event(t=t))

    window = store.get_window(1)
    assert [event.t for event in window] == [3, 4, 5]


def test_memory_window_applies_token_aware_trimming() -> None:
    store = MemoryWindowStore(max_rounds=10, max_prompt_memory_tokens=20)
    store.append(2, _event(t=0, reason="x" * 200))
    store.append(2, _event(t=1, reason="y" * 200))

    window = store.get_window(2)
    assert len(window) == 1
    assert window[0].t == 1
