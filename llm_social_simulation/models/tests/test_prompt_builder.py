import json

from llm_social_simulation.agents.llm.open_resources.prompt import build_open_resources_messages
from llm_social_simulation.models.memory import MemoryEvent
from llm_social_simulation.simulation.gameworld import OpenResourcesObservation


def _obs() -> OpenResourcesObservation:
    return OpenResourcesObservation(
        self_id=3,
        t=12,
        R=37.4,
        P=5.2,
        self_wealth=9.8,
        known_agents=[0, 1, 2, 3],
        info={"dynamics_implemented": True},
    )


def test_prompt_builder_is_deterministic_and_preserves_int_ids() -> None:
    memory = [
        MemoryEvent(
            t=10,
            R=42.0,
            P=4.5,
            self_wealth=8.5,
            action={"harvest": 1.0, "contribute": 0.2},
            reason="steady",
        ),
        MemoryEvent(
            t=11,
            R=40.0,
            P=4.8,
            self_wealth=9.0,
            action={"harvest": 1.1, "contribute": 0.3},
            reason="conserve",
        ),
    ]

    first = build_open_resources_messages(_obs(), memory, run_id="run-1")
    second = build_open_resources_messages(_obs(), memory, run_id="run-1")
    assert first == second

    user_payload = json.loads(first[1]["content"])
    assert user_payload["agent_id"] == 3
    known_agents = user_payload["observation"]["known_agents"]
    assert all(isinstance(agent_id, int) for agent_id in known_agents)


def test_prompt_builder_keeps_memory_in_chronological_order() -> None:
    memory = [
        MemoryEvent(
            t=1,
            R=100.0,
            P=0.0,
            self_wealth=0.0,
            action={"harvest": 0.5, "contribute": 0.0},
            reason=None,
        ),
        MemoryEvent(
            t=2,
            R=99.0,
            P=0.0,
            self_wealth=0.5,
            action={"harvest": 0.6, "contribute": 0.0},
            reason=None,
        ),
    ]

    messages = build_open_resources_messages(_obs(), memory, run_id="run-2")
    user_payload = json.loads(messages[1]["content"])
    assert [m["t"] for m in user_payload["memory_window"]] == [1, 2]


def test_prompt_builder_mentions_contribute_bounds() -> None:
    messages = build_open_resources_messages(_obs(), [], run_id="run-3")
    system_prompt = messages[0]["content"]
    user_payload = json.loads(messages[1]["content"])

    assert "Contribute must not exceed your current self_wealth." in system_prompt
    assert "contribute_max_by_wealth" in user_payload["constraints"]
    assert "recommended_contribute_cap" in user_payload["constraints"]
