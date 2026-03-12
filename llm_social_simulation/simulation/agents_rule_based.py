"""
Backward-compatibility re-export layer.

Canonical rule-based agent implementations live in:
`llm_social_simulation.agents.rule_based`.
"""

from llm_social_simulation.agents.rule_based import (
    CooperativeSustainableAgent,
    GreedyHarvesterAgent,
    OpenResourcesAgent,
    ResourceAwareAdaptiveAgent,
)

__all__ = [
    "CooperativeSustainableAgent",
    "GreedyHarvesterAgent",
    "OpenResourcesAgent",
    "ResourceAwareAdaptiveAgent",
]
