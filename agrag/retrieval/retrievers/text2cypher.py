"""Text2Cypher retriever: generate Cypher from natural language."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.safety import (
    UnsafeCypherError,
    reject_write_cypher,
    strip_cypher_syntax,
)
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings


logger = logging.getLogger(__name__)


def _append_row_limit(query: str, max_rows: int) -> str:
    """Append a LIMIT clause when the query declares none.

    String literals, comments, and backtick identifiers are blanked
    before the LIMIT scan, matching ``reject_write_cypher``, so a
    quoted or commented "LIMIT" inside a predicate cannot suppress
    the bound. The scan is case-insensitive, like Cypher keywords.

    Args:
        query: The generated read query.
        max_rows: Maximum rows the query may return.

    Returns:
        The query, bounded to at most ``max_rows`` rows.
    """
    stripped = strip_cypher_syntax(query)
    if re.search(r"\bLIMIT\b", stripped, flags=re.IGNORECASE):
        return query
    return f"{query} LIMIT {max_rows}"


def _node_id_prop(node: object) -> object | None:
    """Read the ``id`` property from an entity or relationship node.

    Handles plain dicts and ``neo4j`` Node/Relationship objects, which
    expose properties through a Mapping-like ``get``.
    """
    if isinstance(node, dict):
        return node.get("id")
    getter = getattr(node, "get", None)
    if getter is None:
        return None
    try:
        return getter("id")
    except Exception:
        return None


def _node_get(node: object, name: str, default: object = None) -> object:
    """Read a property from a node-like object; return ``default`` on miss.

    A dict with a nested ``properties`` map (the mock-friendly wire
    format used in some test doubles) is treated as a single flat
    namespace, so callers can ask for ``"type"`` whether the value
    is at the top level or under ``properties``. A neo4j
    Node/Relationship is reached through its ``get`` method.
    """
    if isinstance(node, dict):
        if name in node:
            return node[name]
        nested = node.get("properties")
        if isinstance(nested, dict) and name in nested:
            return nested[name]
        return default
    getter = getattr(node, "get", None)
    if getter is None:
        return default
    try:
        value = getter(name)
    except Exception:
        return default
    return value if value is not None else default


def _parse_relationship(value: object) -> Relation | None:
    """Build a Relation from a relationship-shaped row value, or None.

    Accepts a plain dict, a dict carrying ``properties``, or a
    ``neo4j`` Relationship, any of which may expose ``id``, ``type``,
    ``start_id``/``end_id`` either directly or as nested node maps.
    ``source_chunk_ids`` is read from the relationship's properties
    when present; missing fields fall back to safe defaults so a
    partial row still produces a valid Relation. Any parse error
    returns None rather than a partial Relation.
    """
    try:
        rel_id = _node_id_prop(value)
        rel_type = _node_get(value, "type", "")
        if rel_id is None or not rel_type:
            return None
        rel_id = UUID(str(rel_id))

        source_id = _node_get(value, "start_id") or _node_get(value, "source_id")
        target_id = _node_get(value, "end_id") or _node_get(value, "target_id")
        # The driver returns start/end as embedded node objects whose
        # ``id`` is the source/target id.
        if source_id is None:
            start = _node_get(value, "start") or _node_get(value, "a")
            source_id = _node_id_prop(start) if start is not None else None
        if target_id is None:
            end = _node_get(value, "end") or _node_get(value, "b")
            target_id = _node_id_prop(end) if end is not None else None
        if source_id is None or target_id is None:
            return None
        source_id = UUID(str(source_id))
        target_id = UUID(str(target_id))

        properties_value = _node_get(value, "properties")
        properties: dict[str, object] = (
            dict(properties_value) if isinstance(properties_value, dict) else {}
        )
        for k, v in (
            (k, _node_get(value, k))
            for k in ("type", "start_id", "end_id", "id", "source_chunk_ids")
        ):
            if v is not None and k not in properties:
                properties[k] = v

        source_chunk_ids_raw = properties.pop("source_chunk_ids", []) or []
        source_chunk_ids: list[UUID] = []
        if isinstance(source_chunk_ids_raw, list):
            for item in source_chunk_ids_raw:
                try:
                    source_chunk_ids.append(UUID(str(item)))
                except (TypeError, ValueError):
                    continue

        for system_key in ("type", "start_id", "end_id", "id", "source_chunk_ids"):
            properties.pop(system_key, None)

        return Relation(
            id=rel_id,
            type=str(rel_type),
            source_id=source_id,
            target_id=target_id,
            properties=properties,
            source_chunk_ids=source_chunk_ids,
        )
    except Exception:
        return None


def _parse_chunk_node(value: object) -> Chunk | None:
    """Build a Chunk from a chunk-shaped row value, or None.

    Mirrors ``ChunkRetriever._parse_chunk_node``: ``text``,
    ``document_id``, ``index``, ``provenance``, ``heading_path``,
    ``content_kind``, and optional ``embedding`` are read from the
    node's properties. A missing ``document_id`` or malformed
    provenance yields None rather than a partial Chunk.
    """
    from agrag.common.data_models.provenance import (  # noqa: PLC0415
        PageProvenance,
        TextProvenance,
    )

    try:
        node_id = _node_id_prop(value)
        if node_id is None:
            return None

        prov_data = _chunk_provenance_data(_node_get(value, "provenance"))
        if not isinstance(prov_data, dict):
            return None
        provenance = (
            PageProvenance(**prov_data)
            if prov_data.get("kind") == "page"
            else TextProvenance(**prov_data)
        )

        document_id = _node_get(value, "document_id")
        if document_id is None:
            return None

        text_value = _node_get(value, "text", "")
        heading_value = _node_get(value, "heading_path", [])
        raw_kind = _node_get(value, "content_kind", "text")
        content_kind: Any = raw_kind if isinstance(raw_kind, str) else "text"

        index_value = _node_get(value, "index", 0)
        if index_value is None:
            index_int = 0
        elif isinstance(index_value, int):
            index_int = index_value
        elif isinstance(index_value, str):
            try:
                index_int = int(index_value)
            except ValueError:
                index_int = 0
        else:
            # Anything else: best effort; treat as invalid.
            index_int = 0

        heading_list: list[Any] = (
            list(heading_value) if isinstance(heading_value, list) else []
        )

        chunk = Chunk(
            id=UUID(str(node_id)),
            document_id=UUID(str(document_id)),
            index=index_int,
            text=str(text_value) if not isinstance(text_value, str) else text_value,
            provenance=provenance,
            heading_path=heading_list,
            content_kind=content_kind,  # type: ignore[arg-type]
        )
        embedding = _node_get(value, "embedding")
        if isinstance(embedding, list):
            chunk.embedding = list(embedding)
        return chunk
    except Exception:
        return None


def _chunk_provenance_data(raw: object) -> object:
    """Decode a chunk provenance property to a dict, or return the default.

    A string is JSON-decoded; a dict is returned as-is; anything
    else falls back to a default text-provenance dict so a
    malformed value never bubbles up as a parse error.
    """
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {"kind": "text", "char_start": 0, "char_end": 0}


class Text2CypherRetriever(Retriever):
    """Let the agent ask structured questions via generated Cypher.

    Calls a BAML function to generate a read-only Cypher query,
    runs reject_write_cypher as a safety pre-filter, then bounds the
    query with a row limit and a server-side transaction timeout
    before EXPLAIN and execution. Rows that carry an entity id are
    resolved through resolve_entity before becoming a SearchResult;
    relationship and chunk rows are parsed directly. Scalar rows (for
    example counts or property values) cannot become a SearchResult
    and are logged instead of being silently dropped.
    """

    name = "text2cypher"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a Text2CypherRetriever.

        Args:
            graph_store: Where the generated query runs.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._settings = settings or RetrievalSettings()

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Generate and execute a Cypher query for the question.

        Args:
            query: The natural-language question.
            filters: Ignored; text2cypher applies its own filters.
            limit: Maximum results to return.

        Returns:
            SearchResults from the generated query: entity results
                resolved through ``resolve_entity``; relation and chunk
                rows parsed directly. Rows with no entity, relation, or
                chunk item are logged and skipped.
        """
        try:
            cypher_query = await self._generate_cypher(query)
        except Exception:
            return []

        # Safety gate.
        try:
            reject_write_cypher(cypher_query)
        except UnsafeCypherError:
            return []

        # Bound the query: a server-side timeout caps how long a
        # pathological traversal can run, and the row limit caps what
        # the database returns.
        bounded_query = _append_row_limit(
            cypher_query, self._settings.text2cypher_max_rows
        )
        timeout = self._settings.text2cypher_timeout_seconds

        # EXPLAIN (read transaction, so a write would fail here too).
        # Runs on the bounded query so a bad LIMIT placement fails here
        # instead of at execution time.
        try:
            await self._graph_store.execute_read(
                f"EXPLAIN {bounded_query}", timeout=timeout
            )
        except Exception:
            return []

        # Execute for real.
        try:
            rows = await self._graph_store.execute_read(bounded_query, timeout=timeout)
        except Exception:
            return []

        method = f"text2cypher: {cypher_query[:100]}"
        results: list[SearchResult] = []
        for row in rows[:limit]:
            # Try to find an entity id in the row.
            entity_id = self._extract_entity_id(row)
            if entity_id is not None:
                try:
                    entity = await resolve_entity(self._graph_store, entity_id)
                    results.append(SearchResult(item=entity, score=1.0, method=method))
                except Exception:
                    continue
            else:
                relation = self._extract_relation(row)
                if relation is not None:
                    results.append(
                        SearchResult(item=relation, score=1.0, method=method)
                    )
                else:
                    chunk = self._extract_chunk(row)
                    if chunk is not None:
                        results.append(
                            SearchResult(item=chunk, score=1.0, method=method)
                        )
                    else:
                        # A scalar row (count, property value, unknown alias)
                        # cannot become a SearchResult; log it so the answer is
                        # not silently discarded.
                        logger.warning(
                            "text2cypher row has no entity, relation, or chunk "
                            "item and is dropped: %s (query: %.100s)",
                            row,
                            cypher_query,
                        )

        return results

    async def _generate_cypher(self, question: str) -> str:
        """Generate a Cypher query from a question.

        Args:
            question: The natural-language question.

        Returns:
            The generated Cypher query string.
        """
        try:
            from agrag.llm.baml_client import b as baml_client  # noqa: PLC0415

            return await baml_client.GenerateCypherQuery(
                question=question,
                schema_description="Generic schema with Person, "
                "Organization, Location, Event, Product entities "
                "and RELATED_TO, MENTIONED_IN relations.",
            )
        except ImportError:
            return []

    @staticmethod
    def _extract_relation(row: dict) -> Relation | None:
        """Build a Relation from a row whose first value is a relationship.

        Accepts the common RETURN shapes ``[r, ...]`` and
        ``[rel, ...]`` (alias and key both probed) where the value
        carries ``id``, ``type``, plus either ``start_id``/``end_id``
        properties or an embedded start/end node map. Returns None
        for any row shape the retriever cannot interpret.
        """
        for key in ("r", "rel", "relationship"):
            val = row.get(key)
            if val is None:
                continue
            rel = _parse_relationship(val)
            if rel is not None:
                return rel
        return None

    @staticmethod
    def _extract_chunk(row: dict) -> Chunk | None:
        """Build a Chunk from a row whose first value is a Chunk node.

        Accepts the common alias ``c`` and the key ``chunk``. The
        parsing rules mirror ``ChunkRetriever._parse_chunk_node`` so
        a row from either path lands in the same Chunk shape.
        """
        for key in ("c", "chunk"):
            val = row.get(key)
            if val is None:
                continue
            chunk = _parse_chunk_node(val)
            if chunk is not None:
                return chunk
        return None

    @staticmethod
    def _extract_entity_id(row: dict) -> UUID | None:
        """Try to find a UUID entity id in a result row."""
        for key in ("id", "entity_id", "n"):
            val = row.get(key)
            if val is None:
                continue
            if isinstance(val, UUID):
                return val
            if isinstance(val, str):
                try:
                    return UUID(val)
                except ValueError:
                    continue
            try:
                inner_id = val.get("id")
            except (AttributeError, TypeError):
                continue
            if inner_id is not None:
                try:
                    return UUID(str(inner_id))
                except ValueError:
                    continue
        return None
