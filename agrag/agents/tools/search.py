"""Discovery tools: fixed-Recipe searches over SearchEngine.

Each factory returns one LangChain tool bound to an engine, a ledger, and the
caller's base scope. A tool's parameters are exactly the ones it can apply,
and its docstring is the LLM-visible tool description, so it says what the
tool finds and what each argument narrows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agrag.retrieval.errors import ScopeDeniedError


if TYPE_CHECKING:
    from agrag.agents.ledger import Ledger
    from agrag.retrieval.filters import SearchFilters
    from agrag.retrieval.recipes import Recipe
    from agrag.retrieval.search_engine import SearchEngine


SCOPE_DENIED = (
    "Refused: the requested data is outside this agent's permitted scope. "
    "Retry within the scope this agent was given."
)


def scoped_filters(
    base: "SearchFilters | None",
    *,
    labels: list[str] | None = None,
    document_ids: list[str] | None = None,
) -> "SearchFilters | None":
    """Narrow the caller's base scope by a tool call's own filter arguments.

    The base scope is an authorization boundary the model can neither see
    nor override. A tool argument can only narrow it: labels and document
    ids are intersected with the base values, and a request whose
    intersection is empty raises rather than searching wider than the
    caller allowed. Property constraints come from the base scope only and
    are carried through unchanged.

    Args:
        base: The scope the caller set when building the tools, or None
            when the caller set none.
        labels: Labels this call asked to search, or None when the call
            asked for no label restriction.
        document_ids: Document ids this call asked to search, or None when
            the call asked for no document restriction.

    Returns:
        The filters the search should run with, or None when neither the
        base scope nor the call's arguments constrain anything.

    Raises:
        ScopeDeniedError: A requested label or document id is not inside
            the base scope.
    """
    from agrag.retrieval.filters import SearchFilters  # noqa: PLC0415

    if base is None:
        if not labels and not document_ids:
            return None
        return SearchFilters(labels=labels or [], document_ids=document_ids or [])

    if not labels and not document_ids:
        return base

    effective_labels = (
        _intersect(labels, base.labels or None) if labels else list(base.labels)
    )
    effective_document_ids = (
        _intersect(document_ids, base.document_ids or None)
        if document_ids
        else list(base.document_ids)
    )
    return SearchFilters(
        labels=effective_labels,
        relation_types=list(base.relation_types),
        document_ids=effective_document_ids,
        properties=dict(base.properties),
    )


def _intersect(requested: list[str], allowed: list[str] | None) -> list[str]:
    """Return the requested values the caller's scope permits.

    Args:
        requested: Values this tool call asked for.
        allowed: Values the caller's scope permits, or None when the caller
            scoped nothing on this dimension.

    Returns:
        The permitted requested values, in the order they were requested.

    Raises:
        ScopeDeniedError: No requested value is permitted.
    """
    if allowed is None:
        return list(requested)
    permitted = [value for value in requested if value in allowed]
    if not permitted:
        raise ScopeDeniedError
    return permitted


def _narrowed_recipe(
    recipe: "Recipe", *, limit: int, min_score: float | None
) -> "Recipe":
    """Return the shared preset with this call's overrides applied.

    The presets are module-level constants shared by every call, so an
    override is applied with ``model_copy`` rather than in place. A call
    that overrides nothing gets the preset object itself, unchanged.

    Args:
        recipe: The preset this tool runs.
        limit: The result limit this call asked for.
        min_score: The rerank score floor this call asked for, or None.

    Returns:
        The recipe to search with.
    """
    updates: dict[str, Any] = {}
    if limit != recipe.limit:
        updates["limit"] = limit
    if min_score is not None and min_score != recipe.min_score:
        updates["min_score"] = min_score
    return recipe.model_copy(update=updates) if updates else recipe


def render_results(ledger: "Ledger", results: list[Any]) -> str:
    """Render results as cited evidence, or a no-results message.

    Args:
        ledger: The citation ledger for one run.
        results: The results to render.

    Returns:
        One cited line per result, or a no-results message when empty.
    """
    if not results:
        return "No results found."
    return "\n".join(ledger.render(result) for result in results)


def make_search_source_text_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the search_source_text tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool can only narrow.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import CHUNK  # noqa: PLC0415

    @tool("search_source_text")
    async def search_source_text(
        query: str,
        *,
        limit: int = 10,
        document_ids: list[str] | None = None,
    ) -> str:
        """Find passages of source text that mention the query's terms.

        Use this for what a document says, quoted or paraphrased, rather
        than for what the graph knows about an entity.

        Args:
            query: The terms to find in the source text.
            limit: Maximum passages to return.
            document_ids: Restrict the search to these source documents.
                Leave unset to search every document in scope.
        """
        try:
            effective = scoped_filters(filters, document_ids=document_ids)
        except ScopeDeniedError:
            return SCOPE_DENIED

        results = await engine.search(
            query,
            _narrowed_recipe(CHUNK, limit=limit, min_score=None),
            filters=effective,
        )
        return render_results(ledger, results)

    return search_source_text


def make_look_up_entity_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the look_up_entity tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool can only narrow.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import ENTITY  # noqa: PLC0415

    @tool("look_up_entity")
    async def look_up_entity(
        query: str,
        *,
        limit: int = 10,
        labels: list[str] | None = None,
    ) -> str:
        """Find entities the graph holds that match a name or description.

        Returns each entity's name and type with a citation key. Use this to
        discover which entities exist before asking about their properties
        or their neighbours.

        Args:
            query: The entity name or description to look up.
            limit: Maximum entities to return.
            labels: Restrict the search to these entity types, such as
                ["Drug"]. Leave unset to search every type in scope.
        """
        try:
            effective = scoped_filters(filters, labels=labels)
        except ScopeDeniedError:
            return SCOPE_DENIED

        results = await engine.search(
            query,
            _narrowed_recipe(ENTITY, limit=limit, min_score=None),
            filters=effective,
        )
        return render_results(ledger, results)

    return look_up_entity


def make_explore_related_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the explore_related tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool can only narrow.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import HYBRID  # noqa: PLC0415

    @tool("explore_related")
    async def explore_related(
        query: str,
        *,
        limit: int = 10,
        labels: list[str] | None = None,
        document_ids: list[str] | None = None,
    ) -> str:
        """Search entities and source text together for a topic.

        Use this to open an investigation: it returns both kinds of result,
        so the next question can aim at whichever side looks promising.

        Args:
            query: The topic to explore.
            limit: Maximum results to return across both kinds.
            labels: Restrict entity results to these entity types.
            document_ids: Restrict passage results to these source
                documents.
        """
        try:
            effective = scoped_filters(
                filters, labels=labels, document_ids=document_ids
            )
        except ScopeDeniedError:
            return SCOPE_DENIED

        results = await engine.search(
            query,
            _narrowed_recipe(HYBRID, limit=limit, min_score=None),
            filters=effective,
        )
        return render_results(ledger, results)

    return explore_related


def make_answer_from_graph_structure_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the answer_from_graph_structure tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool can only narrow.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import HYBRID_RERANKED  # noqa: PLC0415

    @tool("answer_from_graph_structure")
    async def answer_from_graph_structure(
        query: str,
        *,
        limit: int = 10,
        min_score: float | None = None,
    ) -> str:
        """Answer a question whose evidence is spread across many passages.

        Reranks entity and passage results before returning them, so this is
        the most precise discovery tool and the slowest. Prefer a narrower
        tool when one clearly fits.

        Args:
            query: The question to answer from graph evidence.
            limit: Maximum results to return.
            min_score: Drop results the reranker scores below this, for a
                shorter, higher-precision list. Leave unset to keep the
                configured default threshold.
        """
        results = await engine.search(
            query,
            _narrowed_recipe(HYBRID_RERANKED, limit=limit, min_score=min_score),
            filters=filters,
        )
        return render_results(ledger, results)

    return answer_from_graph_structure


def make_answer_thematic_question_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the answer_thematic_question tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool can only narrow.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import THEMATIC  # noqa: PLC0415

    @tool("answer_thematic_question")
    async def answer_thematic_question(query: str, *, limit: int = 5) -> str:
        """Answer a broad, thematic question from community summaries.

        Communities are clusters of related entities with a written summary,
        so this answers "what is this graph about" questions that no single
        entity or passage answers.

        Args:
            query: The thematic question to answer.
            limit: Maximum community summaries to return.
        """
        results = await engine.search(
            query,
            _narrowed_recipe(THEMATIC, limit=limit, min_score=None),
            filters=filters,
        )
        return render_results(ledger, results)

    return answer_thematic_question


def make_query_graph_directly_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the query_graph_directly tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: Unused; the tool exists only for unscoped agents, so a
            caller scope means make_tools() leaves it out entirely.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    from agrag.retrieval.recipes import TEXT2CYPHER  # noqa: PLC0415

    @tool("query_graph_directly")
    async def query_graph_directly(query: str) -> str:
        """Ask the graph a structural question in one generated query.

        Generates a read-only Cypher query from the graph's schema and
        runs it, for questions no staged tool fits: comparisons across
        entity types, counted patterns, or a relationship shape the
        other tools cannot express. Available only when this agent has
        no caller-set data scope, since a generated query cannot be
        confined to one.

        Args:
            query: The question to translate into one Cypher query.
        """
        results = await engine.search(query, TEXT2CYPHER, filters=filters)
        return render_results(ledger, results)

    return query_graph_directly
