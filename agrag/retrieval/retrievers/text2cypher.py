"""Text2Cypher retriever: generate Cypher from natural language."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.query_value import QueryValue
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


if TYPE_CHECKING:
    from baml_py import ClientRegistry

    from agrag.llm.baml_client.runtime import BamlCallOptions


logger = logging.getLogger(__name__)

# A retry diagnostic is untrusted database output that reaches the next
# generation prompt, so it is bounded and stripped of anything that could
# carry graph content or read as an instruction.
_DIAGNOSTIC_MESSAGE_MAX_CHARS = 400
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_QUOTED_VALUE_PATTERN = re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`")
_CYPHER_CLAUSE_PATTERN = re.compile(
    r"\b(?:MATCH|RETURN|WHERE|WITH|UNWIND|CREATE|MERGE|DELETE|DETACH|SET|"
    r"REMOVE|CALL|YIELD|LIMIT|ORDER\s+BY|SKIP)\b",
    flags=re.IGNORECASE,
)
_INSTRUCTION_MARKERS = (
    "ignore",
    "disregard",
    "forget",
    "instead",
    "you must",
    "you should",
    "do not",
    "don't",
    "system prompt",
    "instruction",
    "assistant",
    "override",
    "pretend",
)


def _format_retry_diagnostic(exc: BaseException) -> str:
    """Build a bounded, sanitized diagnostic for a failed query attempt.

    The generated query, graph values, identifiers, and instruction-like
    phrasing are removed before the text reaches the next generation call.
    What survives is the exception's category plus a short excerpt of its
    message, which the generation prompt delimits as data.

    Args:
        exc: The exception the failed EXPLAIN or execution raised.

    Returns:
        One line naming the exception category, followed by up to 400
        characters of scrubbed message text when any survived.
    """
    category = type(exc).__name__
    message = _scrub_diagnostic_message(str(exc))
    if not message:
        return category
    return f"{category}: {message}"


def _scrub_diagnostic_message(message: str) -> str:
    """Strip unsafe content from a database error message.

    Rewrites UUID-like values and quoted values, then drops any line that
    still carries Cypher clause text or instruction-like phrasing. Surviving
    lines are joined with single spaces, so the result has no newlines to
    break out of the delimited prompt block.

    Args:
        message: The raw exception message.

    Returns:
        At most 400 characters of scrubbed message text, empty when nothing
        safe survived.
    """
    redacted = _UUID_PATTERN.sub("<id>", message)
    redacted = _QUOTED_VALUE_PATTERN.sub("<value>", redacted)
    kept: list[str] = []
    for line in redacted.splitlines():
        if _CYPHER_CLAUSE_PATTERN.search(line):
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in _INSTRUCTION_MARKERS):
            continue
        stripped = line.strip()
        if stripped:
            kept.append(stripped)
    scrubbed = " ".join(kept)
    return scrubbed[:_DIAGNOSTIC_MESSAGE_MAX_CHARS].strip()


# Models routinely wrap a generated query in a markdown code fence. The
# fence is not Cypher, so it would fail EXPLAIN and burn the one retry.
_FENCED_CODE_PATTERN = re.compile(
    r"\A\s*```[A-Za-z0-9_-]*\s*\n?(?P<body>.*?)\n?\s*```\s*\Z", re.DOTALL
)


def _strip_code_fence(text: str) -> str:
    """Return the Cypher inside a markdown code fence, else the text itself.

    Args:
        text: The model's raw response.

    Returns:
        The unwrapped query, with surrounding whitespace removed.
    """
    match = _FENCED_CODE_PATTERN.match(text)
    if match is None:
        return text.strip()
    return match.group("body").strip()


def _baml_call_options() -> "BamlCallOptions":
    """Return the BAML client options the shared ``LLM_*`` config selects.

    Without these options the call uses the generated client's built-in
    OpenAI client, which reads ``OPENAI_API_KEY`` and a fixed model name. An
    environment with no ``LLM_BASE_URL``/``LLM_MODEL_ID`` set returns an
    empty mapping, leaving the call on that built-in client.

    Returns:
        Options carrying a client registry for the configured
        OpenAI-compatible endpoint, or an empty mapping when none is
        configured.
    """
    try:
        from agrag.ingestion.extract import ExtractionLLMSettings  # noqa: PLC0415
        from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415
    except ImportError:
        return {}

    try:
        settings = ExtractionLLMSettings.from_openai_compatible_env()
    except RuntimeError:
        return {}

    return {
        "client_registry": cast(
            "ClientRegistry",
            build_client_registry(settings.clients, strategy=settings.strategy),
        )
    }


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

    Calls a BAML function to generate a read-only Cypher query
    against the graph's declared schema, runs reject_write_cypher as a
    safety pre-filter, then bounds the query with a row limit and a
    server-side transaction timeout before EXPLAIN and execution. A
    query that fails to plan or to execute is regenerated once, carrying
    a bounded, sanitized diagnostic of the failure. Rows that carry an
    entity id are resolved through resolve_entity before becoming a
    SearchResult; relationship and chunk rows are parsed directly, under
    the prompt's own aliases or any alias the model chose instead.
    Scalar rows (for example counts or property values) become cited
    ``QueryValue`` results so direct-query answers are not lost.
    """

    name = "text2cypher"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        schema: GraphSchema,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a Text2CypherRetriever.

        Args:
            graph_store: Where the generated query runs.
            schema: The graph's declared schema. Generation is grounded in
                this schema's labels and relation patterns, so a query the
                graph cannot answer is not generated.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._schema = schema
        self._settings = settings or RetrievalSettings()

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Generate and execute a Cypher query for the question.

        A query that fails to plan or to execute is regenerated once, with a
        bounded, sanitized diagnostic of the first failure attached to the
        generation call. A failure at any stage of the second attempt, or a
        query rejected by the write gate, returns no results rather than
        raising.

        Args:
            query: The natural-language question.
            filters: Ignored; text2cypher applies its own filters.
            limit: Maximum results to return.

        Returns:
            SearchResults from the generated query: entity results
                resolved through ``resolve_entity``; relation, chunk, and
                scalar rows parsed directly.
        """
        try:
            cypher_query = await self._generate_cypher(query)
        except Exception:
            return []

        try:
            rows = await self._execute_query(cypher_query)
        except UnsafeCypherError:
            return []
        except Exception as exc:
            try:
                cypher_query = await self._generate_cypher(
                    query, failure_context=_format_retry_diagnostic(exc)
                )
                rows = await self._execute_query(cypher_query)
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
                        results.append(
                            SearchResult(
                                item=QueryValue(value=dict(row)),
                                score=1.0,
                                method=method,
                            )
                        )

        return results

    async def _execute_query(self, cypher_query: str) -> list[dict[str, Any]]:
        """Gate, bound, plan, and run one generated read query.

        The row limit and the server-side timeout cap a pathological
        traversal, and the query is planned before it runs so a malformed
        one fails here rather than mid-execution.

        Args:
            cypher_query: The generated read query.

        Returns:
            The rows the query returned.

        Raises:
            UnsafeCypherError: The query contains a write clause.
            Exception: The query failed to plan or to execute.
        """
        reject_write_cypher(cypher_query)
        bounded_query = _append_row_limit(
            cypher_query, self._settings.text2cypher_max_rows
        )
        timeout = self._settings.text2cypher_timeout_seconds
        await self._graph_store.execute_read(
            f"EXPLAIN {bounded_query}", timeout=timeout
        )
        return await self._graph_store.execute_read(bounded_query, timeout=timeout)

    async def _generate_cypher(
        self, question: str, *, failure_context: str | None = None
    ) -> str:
        """Generate a Cypher query from a question.

        Args:
            question: The natural-language question.
            failure_context: A sanitized diagnostic from a prior failed
                attempt, or None on the first attempt. The prompt marks it
                as data to repair against, never as instructions.

        Returns:
            The generated Cypher query string.

        Raises:
            ImportError: The BAML client is not installed, so no query
                can be generated. ``retrieve`` turns this into an empty
                result set.
        """
        from agrag.llm.baml_client import b as baml_client  # noqa: PLC0415

        generated = await baml_client.GenerateCypherQuery(
            question=question,
            schema_description=self._schema.to_prompt_description(),
            failure_context=failure_context,
            baml_options=_baml_call_options(),
        )
        return _strip_code_fence(generated)

    @staticmethod
    def _extract_relation(row: dict) -> Relation | None:
        """Build a Relation from a row carrying a relationship.

        Accepts the aliases the generation prompt asks for, then falls
        back to any other value shaped like a relationship: a relationship
        carries ``id``, ``type``, and either ``start_id``/``end_id``
        properties or embedded start/end nodes, which no entity or chunk
        node does. Returns None for any row shape it cannot interpret.
        """
        for key in ("r", "rel", "relationship"):
            val = row.get(key)
            if val is None:
                continue
            rel = _parse_relationship(val)
            if rel is not None:
                return rel
        for key, val in row.items():
            if key == "id":
                continue
            rel = _parse_relationship(val)
            if rel is not None:
                return rel
        return None

    @staticmethod
    def _extract_chunk(row: dict) -> Chunk | None:
        """Build a Chunk from a row carrying a chunk node.

        Accepts the aliases the generation prompt asks for, then falls back
        to any other value shaped like a chunk: ``_parse_chunk_node``
        requires a chunk's own ``id``, ``document_id``, and provenance, so
        an entity or relationship value cannot parse as one. The parsing
        rules mirror ``ChunkRetriever._parse_chunk_node``, so a row from
        either path lands in the same Chunk shape.
        """
        for key in ("c", "chunk"):
            val = row.get(key)
            if val is None:
                continue
            chunk = _parse_chunk_node(val)
            if chunk is not None:
                return chunk
        for key, val in row.items():
            if key == "id":
                continue
            chunk = _parse_chunk_node(val)
            if chunk is not None:
                return chunk
        return None

    @staticmethod
    def _extract_entity_id(row: dict) -> UUID | None:  # noqa: PLR0912
        """Try to find a UUID entity id in a result row.

        Accepts the aliases the generation prompt asks for, then falls back
        to any other value that is an entity node: a model names the
        returned node freely, so a row under an unexpected alias would
        otherwise be dropped. The fallback requires both an id and a name,
        since an entity is the only item this retriever parses that carries
        a name, so a chunk or relationship value cannot be mistaken for
        one.
        """
        for key in ("entity_id", "n"):
            val = row.get(key)
            if val is None:
                continue
            if key == "entity_id" and not isinstance(val, dict):
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

        for key, val in row.items():
            if key in ("id", "entity_id", "n"):
                continue
            node_id = _node_id_prop(val)
            if node_id is None or _node_get(val, "name") is None:
                continue
            try:
                return UUID(str(node_id))
            except ValueError:
                continue
        return None
