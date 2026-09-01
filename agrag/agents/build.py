"""Build the planner/researcher/verifier agent graph."""

import importlib.util
from typing import Any

from agrag.agents.ledger import Ledger
from agrag.agents.model import build_chat_model, build_model_middleware
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.tools import make_tools
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.search_engine import SearchEngine


def build_agent(
    *,
    engine: SearchEngine,
    llm_settings: AgentLLMSettings,
    agent_settings: AgentSettings | None = None,
    filters: SearchFilters | None = None,
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
            build_chat_model. With several clients, the remaining
            ones compose per strategy through agent middleware.
        agent_settings: Loop-level configuration; defaults from
            environment. The recursion limit is enforced as the
            LangGraph ``recursion_limit`` in the invoke config.
        filters: Retrieval scope applied to every tool search,
            e.g. document or tenant constraints. None searches
            unfiltered.

    Returns:
        A compiled agent graph ready for invoke/ainvoke, or a
        simple single-search fallback when deepagents is not
        installed.
    """
    settings = agent_settings or AgentSettings()
    model = build_chat_model(llm_settings.clients[0])
    middleware = build_model_middleware(
        llm_settings.clients, strategy=llm_settings.strategy
    )

    if importlib.util.find_spec("deepagents") is not None:
        return _RunScopedAgent(
            engine=engine,
            model=model,
            settings=settings,
            middleware=middleware,
            filters=filters,
        )

    # Fallback: a simple wrapper when deepagents is not installed,
    # useful for unit testing without the full extra. If deepagents
    # is present but broken, ainvoke raises its import error at call
    # time instead of silently degrading here.
    return _SimpleAgent(model=model, engine=engine, filters=filters)


class _RunScopedAgent:
    """Builds the deepagents graph fresh per run.

    Each ``ainvoke`` call constructs the graph with a new
    ``Ledger`` and tool set so citation state does not span runs,
    and enforces the configured LangGraph recursion limit.
    """

    def __init__(
        self,
        *,
        engine: SearchEngine,
        model: Any,
        settings: AgentSettings,
        middleware: list[Any] | None = None,
        filters: SearchFilters | None = None,
    ) -> None:
        """Construct the wrapper."""
        self._engine = engine
        self._model = model
        self._settings = settings
        self._middleware = middleware or []
        self._filters = filters

    async def ainvoke(self, input_data: dict) -> dict[str, Any]:
        """Delegate to inner agent with a fresh Ledger.

        Args:
            input_data: Dict with ``messages`` key.

        Returns:
            Dict with ``messages`` key containing the answer.
        """
        from deepagents import create_deep_agent  # noqa: PLC0415

        ledger = Ledger()
        tools = make_tools(self._engine, ledger, filters=self._filters)
        agent = create_deep_agent(
            model=self._model,
            tools=tools,
            system_prompt=(
                "You are a research assistant that answers questions "
                "by searching a knowledge graph and citing evidence."
            ),
            middleware=self._middleware,
        )
        return await agent.ainvoke(
            input_data,
            config={"recursion_limit": self._settings.recursion_limit},
        )


class _SimpleAgent:
    """Fallback agent when deepagents is not installed.

    Performs a single hybrid search per invocation, so there is no
    agent loop and ``AgentSettings.recursion_limit`` does not apply.
    """

    def __init__(
        self,
        *,
        model: Any,
        engine: SearchEngine,
        filters: SearchFilters | None = None,
    ) -> None:
        """Construct a simple agent wrapper."""
        self._model = model
        self._engine = engine
        self._filters = filters

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

        results = await self._engine.search(question, HYBRID, filters=self._filters)
        evidence = [ledger.render(r) for r in results]
        answer = (
            "Based on the knowledge graph:\n" + "\n".join(evidence)
            if evidence
            else "No relevant evidence found."
        )
        return {"messages": [{"role": "assistant", "content": answer}]}
