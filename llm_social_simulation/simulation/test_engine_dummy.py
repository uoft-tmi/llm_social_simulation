# llm_social_simulation/simulation/test_engine_dummy.py

from llm_social_simulation.simulation.engine import SimulationEngine

# ---- Dummy implementations ----


class DummyGameworld:
    def get_observation(self, agent_id):
        return {"self_id": agent_id, "neighbors": []}

    def apply_actions(self, actions):
        return {"actions": actions}


class DummyAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def decide(self, obs):
        return {}


def test_engine_runs_dummy_world() -> None:
    engine = SimulationEngine(DummyGameworld(), [DummyAgent(0), DummyAgent(1)])
    history = engine.run(3)
    assert len(history) == 3
    assert all("actions" in tick for tick in history)
