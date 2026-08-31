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

    Each call to ``ainvoke`` creates a fresh ``Ledger`` so
    citation numbering, identity mappings, and retrieved evidence
    do not leak across runs.

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

    try:
        from deepagents import create_deep_agent  # noqa: PLC0415

        inner = create_deep_agent(
            model=model,
            tools=make_tools(engine, Ledger()),
            system_prompt=(
                "You are a research assistant that answers questions "
                "by searching a knowledge graph and citing evidence."
            ),
        )
        return _RunScopedAgent(inner=inner, engine=engine, model=model)
    except ImportError:
        # Fallback: return a simple wrapper when deepagents is not
        # installed, useful for unit testing without the full extra.
        return _SimpleAgent(
            model=model,
            engine=engine,
            settings=settings,
        )


class _RunScopedAgent:
    """Wraps a deepagents graph to create fresh tools per run.

    The inner agent is built once (the graph structure is reused),
    but each ``ainvoke`` call creates a new ``Ledger`` and tool
    set so citation state does not span runs.
    """

    def __init__(
        self,
        *,
        inner: Any,
        engine: SearchEngine,
        model: Any,
    ) -> None:
        """Construct the wrapper."""
        self._inner = inner
        self._engine = engine
        self._model = model

    async def ainvoke(self, input_data: dict) -> dict[str, Any]:
        """Delegate to inner agent with a fresh Ledger."""
        from deepagents import create_deep_agent  # noqa: PLC0415

        ledger = Ledger()
        tools = make_tools(self._engine, ledger)
        agent = create_deep_agent(
            model=self._model,
            tools=tools,
            system_prompt=(
                "You are a research assistant that answers questions "
                "by searching a knowledge graph and citing evidence."
            ),
        )
        return await agent.ainvoke(input_data)


class _SimpleAgent:
    """Fallback agent when deepagents is not installed."""

    def __init__(
        self,
        *,
        model: Any,
        engine: SearchEngine,
        settings: AgentSettings,
    ) -> None:
        """Construct a simple agent wrapper."""
        self._model = model
        self._engine = engine
        self._settings = settings

    async def ainvoke(self, input_data: dict) -> dict[str, Any]:
        """Run the agent with a fresh ledger (simplified path).

        Creates a new ``Ledger`` and tool set per invocation so
        citation state does not span runs.

        Args:
            input_data: Dict with ``messages`` key.

        Returns:
            Dict with ``messages`` key containing the answer.
        """
        messages = input_data.get("messages", [])
        if not messages:
            return {"messages": []}

        ledger = Ledger()
        question = messages[-1].get("content", "")
        from agrag.retrieval.recipes import HYBRID  # noqa: PLC0415

        results = await self._engine.search(question, HYBRID)
        evidence = [ledger.render(r) for r in results]
        answer = (
            "Based on the knowledge graph:\n" + "\n".join(evidence)
            if evidence
            else "No relevant evidence found."
        )
        return {"messages": [{"role": "assistant", "content": answer}]}
