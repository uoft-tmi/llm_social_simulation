"""
Backward-compatibility parser exports.

Canonical parser modules live under:
`llm_social_simulation.agents.llm.<mode>.parser`.
"""

from llm_social_simulation.agents.llm.open_resources.parser import (
    open_resources_response_format,
    parse_open_resources_decision,
)
from llm_social_simulation.agents.llm.open_resources.schema import (
    OpenResourcesActionPayload,
    OpenResourcesDecisionPayload,
    ParsedOpenResourcesDecision,
)

__all__ = [
    "OpenResourcesActionPayload",
    "OpenResourcesDecisionPayload",
    "ParsedOpenResourcesDecision",
    "open_resources_response_format",
    "parse_open_resources_decision",
]
