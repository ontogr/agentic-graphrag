"""Entity-graph tools: resolve a named entity, then walk its relationships.

Each factory returns one LangChain tool bound to an engine, a ledger, and the
caller's base scope. Every tool here resolves its ``entity`` argument through
``SearchEngine.find_entity`` exactly once before doing anything else, so a name
the caller's scope does not cover stops at "Entity not found." instead of
being traversed anyway.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agrag.agents.tools.search import SCOPE_DENIED, render_results
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.relations import TraversalDirection
from agrag.retrieval.errors import ScopeDeniedError


if TYPE_CHECKING:
    from agrag.agents.ledger import Ledger
    from agrag.retrieval.filters import SearchFilters
    from agrag.retrieval.search_engine import SearchEngine


_ENTITY_NOT_FOUND = (
    "Entity not found. Check the name, or search for it with look_up_entity first."
)

# Above this many neighbours, a traversal with no relation_type is reported as
# its relationship types instead of as a neighbour list, so the model narrows
# the traversal rather than reading an undifferentiated fan-out.
_TRAVERSAL_WIDE_FANOUT = 20


def _entity_item(result: SearchResult) -> Entity | ResolvedEntity | None:
    """Return a result's item when it is entity-like, else None.

    ``find_entity`` yields an ``Entity`` or a ``ResolvedEntity``; this
    narrows the wider union ``SearchResult.item`` carries for the
    rendering below, which needs an entity's own name and label.

    Args:
        result: The result to read.

    Returns:
        The entity-like item, or None when the result wraps something
        else.
    """
    if isinstance(result.item, (Entity, ResolvedEntity)):
        return result.item
    return None


def _too_wide_message(name: str, count: int, types: list[str]) -> str:
    """Render the fallback for a traversal too wide to list neighbours.

    Args:
        name: The resolved entity's name.
        count: How many neighbours the traversal found.
        types: The distinct relationship types attached to the entity.

    Returns:
        Text naming the relationship types to narrow by.
    """
    if not types:
        return (
            f"{name} has more than {_TRAVERSAL_WIDE_FANOUT} neighbours and no "
            f"findable relationship types. Ask for fewer results with "
            f"min_score, or name a relation_type you already expect."
        )
    return (
        f"{name} has {count} neighbours, too many to list. Its relationship "
        f"types are: {', '.join(sorted(types))}. Call this tool again with "
        f"relation_type set to one of them."
    )


def make_list_relationship_types_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the list_relationship_types tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool cannot widen.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool("list_relationship_types")
    async def list_relationship_types(
        entity: str,
        relation_type_filter: str | None = None,
    ) -> str:
        """List the relationship types attached to an entity.

        Use this to find out how an entity is connected before traversing,
        and to pick a relation_type for find_related_entities or
        traverse_from_entity.

        Args:
            entity: The entity name to look up, such as "Acme Corp".
            relation_type_filter: Only report this relationship type, when
                you are checking whether it is present.
        """
        resolved = await engine.find_entity(entity, filters=filters)
        if resolved is None:
            return _ENTITY_NOT_FOUND

        item = _entity_item(resolved)
        name = item.name if item is not None else entity
        types = await engine.list_relationship_types(
            resolved, relation_type_filter=relation_type_filter, filters=filters
        )
        if not types:
            return f"No relationships found on {name}."
        return f"Relationship types on {name}: " + ", ".join(sorted(types))

    return list_relationship_types


def make_find_related_entities_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the find_related_entities tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool cannot widen and
            which also bounds the traversal, so a resolved entity cannot
            reach neighbours outside its caller's scope.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool("find_related_entities")
    async def find_related_entities(
        entity: str,
        relation_type: str,
        direction: TraversalDirection = "both",
        community_expand: bool = False,
    ) -> str:
        """Find the entities one relationship type away from an entity.

        Use this when you already know which relationship to follow, such
        as the drugs that treat a disease. Call list_relationship_types
        first if you do not.

        Args:
            entity: The entity name to start from.
            relation_type: The relationship to follow, in upper case, such
                as "TREATS".
            direction: Which way to follow it. "outgoing" means the entity
                is the relationship's source, "incoming" means it is the
                target, "both" means either.
            community_expand: Also return the summaries of communities the
                entity belongs to, for surrounding context.
        """
        resolved = await engine.find_entity(entity, filters=filters)
        if resolved is None:
            return _ENTITY_NOT_FOUND

        try:
            results = await engine.traverse(
                resolved,
                relation_type=relation_type,
                direction=direction,
                community_expand=community_expand,
                filters=filters,
            )
        except ScopeDeniedError:
            return SCOPE_DENIED
        return render_results(ledger, results)

    return find_related_entities


def make_describe_entity_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the describe_entity tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool cannot widen.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool("describe_entity")
    async def describe_entity(entity: str) -> str:
        """Show an entity's own recorded properties.

        Use this for what the graph stores about a single entity, such as
        its description or identifiers. It returns no neighbours: use
        find_related_entities or traverse_from_entity for those.

        Args:
            entity: The entity name to describe.
        """
        resolved = await engine.find_entity(entity, filters=filters)
        if resolved is None:
            return _ENTITY_NOT_FOUND

        item = _entity_item(resolved)
        if item is None:
            return _ENTITY_NOT_FOUND

        key = ledger.cite(resolved)
        properties = item.properties
        body = (
            "\n".join(f"- {name}: {value}" for name, value in properties.items())
            if properties
            else "(no properties)"
        )
        return f"[{key}] {item.name} ({item.label})\n{body}"

    return describe_entity


def make_traverse_from_entity_tool(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Build the traverse_from_entity tool.

    Args:
        engine: The SearchEngine the tool calls.
        ledger: The citation ledger for one run.
        filters: The caller's base scope, which the tool cannot widen and
            which also bounds the traversal.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool("traverse_from_entity")
    async def traverse_from_entity(
        entity: str,
        relation_type: str | None = None,
        direction: TraversalDirection = "both",
        depth: int = 1,
    ) -> str:
        """Walk outward from an entity, one or more relationships at a time.

        Use this to explore how an entity is connected when you do not
        already know which relationship to follow. With no relation_type it
        returns the entity's neighbours, or, when there are too many, the
        relationship types to narrow by instead.

        Args:
            entity: The entity name to start from.
            relation_type: Follow only this relationship, in upper case,
                such as "TREATS". Omit it to follow every relationship.
            direction: Which way to follow relationships. "outgoing" means
                the entity is the relationship's source, "incoming" means
                it is the target, "both" means either.
            depth: How many relationship hops to walk, from 1 up. Higher
                depths reach further but pull in less relevant entities.
        """
        resolved = await engine.find_entity(entity, filters=filters)
        if resolved is None:
            return _ENTITY_NOT_FOUND

        try:
            if relation_type is None:
                results = await engine.traverse(
                    resolved,
                    direction=direction,
                    depth=depth,
                    limit=_TRAVERSAL_WIDE_FANOUT + 1,
                    filters=filters,
                )
                if len(results) > _TRAVERSAL_WIDE_FANOUT:
                    item = _entity_item(resolved)
                    types = await engine.list_relationship_types(
                        resolved, filters=filters
                    )
                    return _too_wide_message(
                        item.name if item is not None else entity,
                        len(results),
                        types,
                    )
                return render_results(ledger, results)

            results = await engine.traverse(
                resolved,
                relation_type=relation_type,
                direction=direction,
                depth=depth,
                filters=filters,
            )
        except ScopeDeniedError:
            return SCOPE_DENIED
        return render_results(ledger, results)

    return traverse_from_entity
