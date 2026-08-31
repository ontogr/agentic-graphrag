"""Subagent definitions: planner, researcher, verifier."""

from typing import Any

from agrag.agents.prompts import (
    PLANNER_SYSTEM,
    RESEARCHER_SYSTEM,
    VERIFIER_SYSTEM,
)


def make_planner_prompt() -> dict[str, Any]:
    """Return the planner subagent config.

    Returns:
        A dict with system_prompt key for the planner role.
    """
    return {"system_prompt": PLANNER_SYSTEM}


def make_researcher_prompt() -> dict[str, Any]:
    """Return the researcher subagent config.

    Returns:
        A dict with system_prompt key for the researcher role.
    """
    return {"system_prompt": RESEARCHER_SYSTEM}


def make_verifier_prompt() -> dict[str, Any]:
    """Return the verifier subagent config.

    Returns:
        A dict with system_prompt key for the verifier role.
    """
    return {"system_prompt": VERIFIER_SYSTEM}
