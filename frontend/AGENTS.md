# AGENTS.md

## Project goal
This repo focuses on the Open Resources simulation as the primary research environment.
Do not rewrite the repo from scratch.
Preserve existing architecture whenever possible.
Prefer incremental refactors over large replacements.

## Engineering rules
- Keep the existing repo and evolve it in-place.
- Avoid breaking current functionality unless necessary.
- Prefer additive changes around Open Resources policies, diagnostics, and experiments.
- Make small, reviewable commits.
- Before editing, inspect the current repo structure and reuse existing abstractions.

## Implementation priorities
1. Improve Open Resources policy quality and safety.
2. Strengthen experiment reproducibility (seeds, configs, summaries).
3. Expand deterministic baselines for stronger LLM comparisons.
4. Improve diagnostics and replay payload quality for analysis.

## Constraints
- No premature UI work.
- No premature animation work.
- No premature OpenClaw coupling.
- No unrelated new simulation modes.
- No heavy redesign of unrelated modules.

## Testing expectations
- Add or update unit tests for all new core modules.
- Prefer deterministic tests.
- Add one end-to-end smoke test for a short Open Resources run.

## Code style
- Prefer clear, typed Python.
- Prefer dataclasses or Pydantic models for schemas.
- Keep modules small and composable.
- Document all new public classes/functions.