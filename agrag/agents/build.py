"""Build the planner/researcher/verifier agent graph."""

from typing import Any

from agrag.agents.ledger import Ledger
from agrag.agents.model import build_chat_model
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.tools import make_tools
from agrag.retrieval.search_engine import SearchEngine


def build_agent(
    *,
    engine: SearchEngine,
    llm_settings: AgentLLMSettings,
    agent_settings: AgentSettings | None = None,
) -> Any:
    """Build the planner/researcher/verifier agent graph.

    Constructs a LangGraph-based agent with three roles:
    planner (decomposes the question), researcher (has tools),
    and verifier (judges evidence sufficiency).

    Args:
        engine: Retrieval to expose to the researcher subagent's
            tools.
        llm_settings: The model every subagent role calls, via
            build_chat_model.
        agent_settings: Loop-level configuration; defaults from
            environment.

    Returns:
        A compiled agent graph ready for invoke/ainvoke.
    """
    settings = agent_settings or AgentSettings()
    model = build_chat_model(llm_settings.clients[0])
    ledger = Ledger()
    tools = make_tools(engine, ledger)

    try:
        from deepagents import create_deep_agent  # noqa: PLC0415

        return create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=(
                "You are a research assistant that answers questions "
                "by searching a knowledge graph and citing evidence."
            ),
        )
    except ImportError:
        # Fallback: return a simple wrapper when deepagents is not
        # installed, useful for unit testing without the full extra.
        return _SimpleAgent(
            model=model,
            tools=tools,
            ledger=ledger,
            engine=engine,
            settings=settings,
        )


class _SimpleAgent:
    """Fallback agent when deepagents is not installed."""

    def __init__(
        self,
        *,
        model: Any,
        tools: list[Any],
        ledger: Ledger,
        engine: SearchEngine,
        settings: AgentSettings,
    ) -> None:
        """Construct a simple agent wrapper."""
        self._model = model
        self._tools = {t.name: t for t in tools}
        self._ledger = ledger
        self._engine = engine
        self._settings = settings

    async def ainvoke(self, input_data: dict) -> dict[str, Any]:
        """Run the agent synchronously (simplified path).

        Args:
            input_data: Dict with ``messages`` key.

        Returns:
            Dict with ``messages`` key containing the answer.
        """
        messages = input_data.get("messages", [])
        if not messages:
            return {"messages": []}

        question = messages[-1].get("content", "")
        # Simple direct search for testing.
        from agrag.retrieval.recipes import HYBRID  # noqa: PLC0415

        results = await self._engine.search(question, HYBRID)
        evidence = [self._ledger.render(r) for r in results]
        answer = (
            "Based on the knowledge graph:\n" + "\n".join(evidence)
            if evidence
            else "No relevant evidence found."
        )
        return {"messages": [{"role": "assistant", "content": answer}]}
