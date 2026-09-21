"""Subagent specs for the researcher and verifier roles.

Each spec is a SubAgent-shaped dict for ``create_deep_agent``'s
``subagents=`` list. Both roles run isolated: they see only the task
description the planner delegates with, so each spec carries its own
middleware explicitly — an isolated subagent does not inherit the
parent agent's middleware.
"""

from typing import Any

from agrag.agents.prompts import RESEARCHER_SYSTEM, VERIFIER_SYSTEM
from agrag.agents.verification import VerificationResult
from agrag.common.data_models.graph_schema import GraphSchema


def make_researcher_spec(
    tools: list[Any], middleware: list[Any], schema: GraphSchema
) -> dict[str, Any]:
    """Build the researcher subagent spec.

    Args:
        tools: The tools this subagent may call.
        middleware: Middleware for this subagent's own model calls. Not
            inherited from the parent agent -- DeepAgents reads only this
            key for an isolated-mode subagent, never the top-level agent's
            own middleware.
        schema: Fills the compact schema summary into RESEARCHER_SYSTEM.

    Returns:
        A SubAgent-shaped dict for create_deep_agent's subagents= list.
    """
    return {
        "name": "researcher",
        "description": "Researches a sub-question using graph tools.",
        "tools": tools,
        "middleware": middleware,
        "system_prompt": RESEARCHER_SYSTEM.replace(
            "{schema_summary}", schema.to_compact_summary()
        ),
    }


def make_verifier_spec(middleware: list[Any]) -> dict[str, Any]:
    """Build the verifier subagent spec.

    Args:
        middleware: Middleware for this subagent's own model calls. Not
            inherited from the parent agent -- DeepAgents reads only this
            key for an isolated-mode subagent, never the top-level agent's
            own middleware.

    Returns:
        A SubAgent-shaped dict for create_deep_agent's subagents= list.
        tools is the explicit empty list, not omitted -- an omitted key
        would inherit the parent's tools instead of granting none.
    """
    return {
        "name": "verifier",
        "description": "Checks whether researcher findings answer a question.",
        "tools": [],
        "middleware": middleware,
        "response_format": VerificationResult,
        "system_prompt": VERIFIER_SYSTEM,
        "mode": "isolated",
    }
