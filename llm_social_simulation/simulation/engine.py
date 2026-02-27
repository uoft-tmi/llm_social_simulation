# simulation/engine.py
class SimulationEngine:
    def __init__(self, gameworld, agents):
        self.gameworld = gameworld
        self.agents = agents
        self.history = []

    def run(self, rounds: int, stop_on_collapse: bool = False):
        for _ in range(rounds):
            actions = {}

            for agent in self.agents:
                obs = self.gameworld.get_observation(agent.agent_id)
                actions[agent.agent_id] = agent.decide(obs)

            tick = self.gameworld.apply_actions(actions)
            self.history.append(tick)
            if stop_on_collapse and bool(getattr(tick, "info", {}).get("collapsed")):
                break

        return self.history
