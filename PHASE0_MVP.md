# Phase 0 – MVP Goal (Frozen)

## Goal (What we must achieve)
- Run 10 agents on a fixed small-world network
- Iterated Prisoner’s Dilemma for 20–30 rounds
- Output:
  - cooperation rate over time
  - final wealth per agent

## Non-goals (Explicitly NOT doing)
- No LLM
- No caching
- No dynamic graph
- No dashboard
- No agent memory

---

## Architecture (Mental Model)

SimulationEngine
  -> Gameworld (single source of truth)
     -> Agents (stateless decision functions)

Rules:
1. Gameworld owns all state and history
2. Agents are pure functions: observation -> action
3. Engine only orchestrates

---

## Interfaces (DO NOT CHANGE)

### Observation (Gameworld -> Agent)
```python
{
  self_id: int,
  neighbors: List[int],
  last_actions_from_neighbors: Dict[int, "C"|"D"],
  self_wealth: int,
  round: int
}
