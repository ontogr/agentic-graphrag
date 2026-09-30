"""Agentic layer: planner/researcher/verifier over SearchEngine.

``build_agent`` is imported lazily because it needs the optional ``agents``
extra. Importing this package does not require that extra.
"""

from typing import TYPE_CHECKING, Any

from agrag.agents.errors import AgentMissingExtraError
from agrag.agents.ledger import Ledger
from agrag.agents.result import AgentRunResult
from agrag.agents.settings import AgentLLMSettings, AgentSettings


if TYPE_CHECKING:
    from agrag.agents.build import build_agent


def __getattr__(name: str) -> Any:
    """Load the optional agent builder when a caller requests it."""
    if name != "build_agent":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from agrag.agents.build import build_agent  # noqa: PLC0415

    return build_agent


__all__ = [
    "AgentLLMSettings",
    "AgentMissingExtraError",
    "AgentRunResult",
    "AgentSettings",
    "Ledger",
    "build_agent",
]
