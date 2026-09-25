"""Result type returned by an agent run."""

from typing import Any, TypedDict

from agrag.agents.ledger import Ledger


class AgentRunResult(TypedDict):
    """Result of one agent run.

    The deep-agent path also passes through the other keys of the LangGraph
    state at runtime; only the keys below are part of the contract.

    Attributes:
        messages: The conversation, ending with the assistant's answer.
        ledger: Citation keys assigned during this run. Use
            ``ledger.resolve(key)`` to get the evidence behind a key.
    """

    messages: list[Any]
    ledger: Ledger
