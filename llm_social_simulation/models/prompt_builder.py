"""
Backward-compatibility prompt builder exports.

Canonical prompt builders live under:
`llm_social_simulation.agents.llm.<mode>.prompt`.
"""

from llm_social_simulation.agents.llm.open_resources.prompt import build_open_resources_messages

__all__ = ["build_open_resources_messages"]
