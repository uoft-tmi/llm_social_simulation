# LLM Social Simulation — Project Roadmap

## Phase 0 — MVP: End-to-End Simulation Loop (Closed Loop + Tests)

**Status:** In progress (late stage)

### Goal

Build a minimal but complete simulation framework that can run Iterated Prisoner’s
Dilemma (IPD) on a fixed graph, produce analyzable outputs, and pass automated tests.

Phase 0 establishes a stable foundation or internal environment for all later phases.

### Core Capabilities

- Run multi-round IPD on a fixed graph
- Output:
  - Cooperation rate per round (time series)
  - Final wealth distribution
- Simulation-related tests pass (smoke tests)


### Deliverables (Minimal Set)
#### SimulationEngine
- Deterministic round-based orchestration
- Pull observations from Gameworld
- Collect agent actions and apply them each round
- Append-only history of TickResult

#### Gameworld
Single source of truth for:
- Agent graph (adjacency list)
- Wealth accumulation
- Last-round actions
- Local observation generation per agent
- Payoff computation using Prisoner’s Dilemma matrix
  
#### Agents
- `BaseAgent(agent_id)`
- `decide(observation) -> Dict[neighbor_id, action]`
- At least two strategies implemented:
  - Always Cooperate
  - Always Defect
  - (Preferred) Tit-for-Tat

#### Simulation Entry Point (optional)
- `run_mvp.py`
- Single official entry point for running the Phase 0 MVP

#### Tests
- `test_gameworld_smoke.py`
- `test_engine_dummy.py`
- All simulation tests pass under `pytest`


### Acceptance Criteria

- The following command runs successfully from the repo root:
  ```bash
  python -m llm_social_simulation.simulation.run_mvp
  ```
- Output includes: Cooperation rate over time and final wealth per agent
- pytest passes
  
## Phase 1 -- Small-World Networks & Config-Driven Experiments
## Phase 2 -- Baselines, Norms, and Measurement Validity (Pre-LLM)
Purpose: Establish controls so LLM behavior can be isolated later.
## Phase 3 -- LLM Agents, Communication, and Dynamic Networks
Purpose: Study how LLMs behave as social agents under constraints.


