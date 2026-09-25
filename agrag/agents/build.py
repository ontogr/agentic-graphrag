"""Build the planner/researcher/verifier agent graph."""

import importlib.util
from typing import Any

from opentelemetry.trace import Tracer

from agrag.agents.harness import ensure_harness_profile, model_provider_key
from agrag.agents.ledger import Ledger
from agrag.agents.middleware import ResearchAttemptLimiter
from agrag.agents.model import build_chat_model, build_model_middleware
from agrag.agents.prompts import PLANNER_SYSTEM, SIMPLE_ANSWER_SYSTEM
from agrag.agents.result import AgentRunResult
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.subagents import make_researcher_spec, make_verifier_spec
from agrag.agents.tools import make_tools
from agrag.agents.tracing import require_tracing, run_callbacks
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.search_engine import SearchEngine


def build_agent(
    *,
    engine: SearchEngine,
    llm_settings: AgentLLMSettings,
    agent_settings: AgentSettings | None = None,
    filters: SearchFilters | None = None,
    graph_schema: GraphSchema | None = None,
    tracer: Tracer | None = None,
) -> Any:
    """Build the planner/researcher/verifier agent graph.

    Constructs a LangGraph-based agent with three roles:
    planner (decomposes the question), researcher (has tools),
    and verifier (judges evidence sufficiency and returns a
    structured verdict).

    Each call to ``ainvoke`` creates a fresh ``Ledger`` so
    citation numbering, identity mappings, and retrieved evidence
    do not leak across runs, and a fresh ``ResearchAttemptLimiter``
    so one question's retry budget does not spend another's.

    Args:
        engine: Retrieval to expose to the researcher subagent's
            tools.
        llm_settings: The model every subagent role calls, via
            build_chat_model. With several clients, the remaining
            ones compose per strategy through agent middleware.
        agent_settings: Loop-level configuration; defaults from
            environment. The recursion limit is enforced as the
            LangGraph ``recursion_limit`` in the invoke config, and
            ``max_research_attempts`` bounds how many times the
            planner may re-research after an INSUFFICIENT verdict.
        filters: Retrieval scope applied to every tool search,
            e.g. document or tenant constraints. None searches
            unfiltered. A non-empty scope also removes the
            ``query_graph_directly`` tool, since a generated query
            cannot be confined to a scope.
        graph_schema: The schema the researcher prompt and the
            ``query_graph_directly`` tool describe. None uses the
            engine's own resolved schema; a value that differs from
            the engine's raises, so the prompt cannot describe a
            graph the engine does not search.
        tracer: Receives OpenInference spans for every ``ainvoke``,
            including the researcher and verifier subagents' tool and
            model calls. None emits no spans. Spans carry the question
            and the evidence text; set ``OPENINFERENCE_HIDE_INPUTS`` or
            ``OPENINFERENCE_HIDE_OUTPUTS`` to hide them.

    Returns:
        An agent whose ``ainvoke`` returns an ``AgentRunResult``: the
        run's ``messages`` plus its ``ledger``, which maps each
        citation key in the answer back to its evidence. When
        deepagents is not installed, a single-search-plus-synthesis
        fallback with the same result shape.

    Raises:
        AgentMissingExtraError: ``tracer`` is set but the ``observability``
            extra is not installed.
        ValueError: ``graph_schema`` differs from the engine's schema.
    """
    if tracer is not None:
        require_tracing()
    settings = agent_settings or AgentSettings()
    model = build_chat_model(llm_settings.clients[0])
    middleware = build_model_middleware(
        llm_settings.clients, strategy=llm_settings.strategy
    )
    schema = engine.graph_schema
    if graph_schema is not None and graph_schema != schema:
        raise ValueError(
            "graph_schema does not match the engine's schema "
            f"('{schema.name}'); the researcher prompt and the engine "
            "must describe the same graph"
        )

    if importlib.util.find_spec("deepagents") is not None:
        return _RunScopedAgent(
            engine=engine,
            model=model,
            settings=settings,
            middleware=middleware,
            filters=filters,
            graph_schema=schema,
            model_provider=model_provider_key(llm_settings.clients[0].provider),
            tracer=tracer,
        )

    # Fallback: a simple wrapper when deepagents is not installed,
    # useful for unit testing without the full extra. If deepagents
    # is present but broken, ainvoke raises its import error at call
    # time instead of silently degrading here.
    return _SimpleAgent(model=model, engine=engine, filters=filters, tracer=tracer)


class _RunScopedAgent:
    """Builds the deepagents graph fresh per run.

    Each ``ainvoke`` call constructs the graph with a new
    ``Ledger``, a new tool set, and a new
    ``ResearchAttemptLimiter`` so citation state and the retry
    budget do not span runs, and enforces the configured LangGraph
    recursion limit.
    """

    def __init__(
        self,
        *,
        engine: SearchEngine,
        model: Any,
        settings: AgentSettings,
        middleware: list[Any] | None = None,
        filters: SearchFilters | None = None,
        graph_schema: GraphSchema | None = None,
        model_provider: str = "",
        tracer: Tracer | None = None,
    ) -> None:
        """Construct the wrapper."""
        self._engine = engine
        self._model = model
        self._settings = settings
        self._middleware = middleware or []
        self._filters = filters
        self._graph_schema = (
            graph_schema if graph_schema is not None else engine.graph_schema
        )
        self._model_provider = model_provider
        self._tracer = tracer

    async def ainvoke(self, input_data: dict) -> AgentRunResult:
        """Delegate to inner agent with a fresh Ledger and limiter.

        Builds the planner with the researcher and verifier as
        subagents. The planner sees the task tool for delegation and
        carries the attempt limiter; the researcher carries the
        caller's tools and the engine's schema summary; the verifier
        returns a structured verdict.

        Args:
            input_data: Dict with ``messages`` key.

        Returns:
            The graph's final state with this run's ``ledger`` added.
        """
        from deepagents import create_deep_agent  # noqa: PLC0415

        ensure_harness_profile(self._model_provider)
        ledger = Ledger()
        tools = make_tools(self._engine, ledger, filters=self._filters)
        researcher = make_researcher_spec(tools, self._middleware, self._graph_schema)
        verifier = make_verifier_spec(self._middleware)
        limiter = ResearchAttemptLimiter(self._settings.max_research_attempts)
        planner_system = PLANNER_SYSTEM.replace(
            "{max_research_attempts}", str(self._settings.max_research_attempts)
        )

        # Annotated, not typed against deepagents' own SubAgent: importing
        # that type here would make this module require the optional
        # dependency at import time. The specs are SubAgent-shaped dicts.
        subagents: list[Any] = [researcher, verifier]
        agent = create_deep_agent(
            model=self._model,
            system_prompt=planner_system,
            subagents=subagents,
            middleware=[*self._middleware, limiter],
        )
        result = await agent.ainvoke(
            input_data,
            config={
                "recursion_limit": self._settings.recursion_limit,
                "callbacks": run_callbacks(self._tracer),
            },
        )
        return {**result, "ledger": ledger}


class _SimpleAgent:
    """Fallback agent when deepagents is not installed.

    Performs a single hybrid search per invocation, then one LLM
    call to synthesize a cited answer from the results -- still no
    agent loop, tool calls, or multi-client composition
    (``build_model_middleware``'s fallback/round-robin strategies
    wrap ``create_deep_agent``'s loop, not a bare model call, and
    this class already only receives ``clients[0]``). There is no
    agent loop, so ``AgentSettings.recursion_limit`` does not apply.
    """

    def __init__(
        self,
        *,
        model: Any,
        engine: SearchEngine,
        filters: SearchFilters | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Construct a simple agent wrapper."""
        self._model = model
        self._engine = engine
        self._filters = filters
        self._tracer = tracer

    async def ainvoke(self, input_data: dict) -> AgentRunResult:
        """Run the agent with a fresh ledger (simplified path).

        Creates a new ``Ledger`` and tool set per invocation so
        citation state does not span runs. Runs one search, then one
        LLM call to synthesize a cited answer from the results.

        Args:
            input_data: Dict with ``messages`` key.

        Returns:
            Dict with ``messages`` containing the answer and this run's
            ``ledger``.
        """
        ledger = Ledger()
        messages = input_data.get("messages", [])
        if not messages:
            return {"messages": [], "ledger": ledger}

        question = messages[-1].get("content", "")
        from agrag.retrieval.recipes import HYBRID  # noqa: PLC0415

        results = await self._engine.search(question, HYBRID, filters=self._filters)
        evidence = [ledger.render(r) for r in results]
        if not evidence:
            return {
                "messages": [
                    {"role": "assistant", "content": "No relevant evidence found."}
                ],
                "ledger": ledger,
            }

        response = await self._model.ainvoke(
            [
                {"role": "system", "content": SIMPLE_ANSWER_SYSTEM},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nEvidence:\n"
                    + "\n".join(evidence),
                },
            ],
            config={"callbacks": run_callbacks(self._tracer)},
        )
        return {
            "messages": [{"role": "assistant", "content": response.text}],
            "ledger": ledger,
        }
