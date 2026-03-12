# AGENTS.md

## Project goal
This repo is evolving from a round-based LLM social simulation into a small open-world society simulator.
Do not rewrite the repo from scratch.
Preserve existing architecture whenever possible.
Prefer incremental refactors over large replacements.

## Current migration objective
Build a minimal open-world core inside the current repository:
- multiple locations / zones
- agent positions
- local observations
- richer actions
- replay-friendly event logs

Do NOT integrate OpenClaw deeply yet.
Only create an adapter boundary for future OpenClaw integration.

## Engineering rules
- Keep the existing repo and evolve it in-place.
- Avoid breaking current functionality unless necessary.
- Prefer additive changes:
  - keep old open-resources mode if possible
  - add new open-world mode beside it
- Make small, reviewable commits.
- Before editing, inspect the current repo structure and reuse existing abstractions.

## Implementation priorities
1. Define schemas:
   - Observation
   - Action
   - Event
2. Create minimal open-world state representation.
3. Build a deterministic simulation loop that can run without LLMs.
4. Add a rule-based agent baseline.
5. Add LLM-agent compatibility layer.
6. Add OpenClaw adapter stubs only after the above works.

## Constraints
- No premature UI work.
- No premature animation work.
- No premature OpenClaw coupling.
- No giant map.
- No combat system unless already present.
- No heavy redesign of unrelated modules.

## Testing expectations
- Add or update unit tests for all new core modules.
- Prefer deterministic tests.
- Add one end-to-end smoke test for a short open-world run.

## Desired open-world MVP
World:
- 8 to 12 locations
- adjacency graph
- per-location renewable resources

Agents:
- id
- position
- inventory
- energy
- wealth
- memory summary
- persona tag

Actions:
- move
- gather
- trade
- talk
- rest

Observation model:
- current location
- nearby locations
- local resources
- nearby agents
- recent local events

## OpenClaw boundary
Design an adapter layer only.
OpenClaw should eventually manage agents / routing / sessions, but not own the world logic.
The repo’s simulation engine remains the source of truth.

## Code style
- Prefer clear, typed Python.
- Prefer dataclasses or Pydantic models for schemas.
- Keep modules small and composable.
- Document all new public classes/functions.