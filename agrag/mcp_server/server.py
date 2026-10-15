"""Build the local MCP server that exposes the evidence operations as tools.

Each tool is a thin layer over the functions in ``agrag.evidence``. The layer
adds the trusted scope from settings, output limits, and the error mapping. It
has no write path.

Semantic and hybrid search need the same ``EMBEDDING_*`` settings that ingestion
used. Each semantic or hybrid call compares the query embedder's dimension with
the Chunk vector index. On a dimension mismatch the semantic leg does not run.
Equal dimensions do not establish that the embedding models are the same.
"""

import logging
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, Any, TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.evidence import (
    CitationResult,
    DiscoveryHit,
    DiscoveryLeg,
    DiscoveryMode,
    DiscoveryResult,
    DiscoveryStatus,
    FetchResult,
    FetchStatus,
    LegFailure,
)
from agrag.cypher.schema import vector_index_dimensions_query
from agrag.embedding.base import Embedder
from agrag.evidence import check_citations as verify_citations
from agrag.evidence import discover, fetch
from agrag.graphdb.base import GraphStore
from agrag.mcp_server.settings import McpServerSettings


_LOGGER = logging.getLogger(__name__)
_SERVER_NAME = "agrag-evidence"
_STORE_UNAVAILABLE = "evidence store unavailable"
_EMBEDDER_UNAVAILABLE = "the query embedding model could not be loaded"
_EMBEDDING_MISMATCH = (
    "the query embedding model does not match the stored vectors; set the same "
    "EMBEDDING_* settings that ingestion used or use lexical mode"
)
_EMBEDDING_PROPERTY = "embedding"
_READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass
class _Session:
    """State that lives as long as the server process.

    Attributes:
        fetched_ids: Evidence ids that fetch returned in full. Citation checks
            trace against this record. It is not persisted, so a restart clears
            it.
    """

    fetched_ids: set[str] = field(default_factory=set)


def _store_lifespan(
    store: GraphStore,
) -> Callable[[MCPServer], AbstractAsyncContextManager[_Session]]:
    """Return a lifespan that connects the store once per server process.

    Args:
        store: The graph store the server reads. The lifespan connects it but
            does not close it.

    Returns:
        A lifespan factory for ``MCPServer``.
    """

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[_Session]:
        try:
            await store.connect()
        except Exception:
            _LOGGER.exception("Could not connect to the evidence store")
            raise
        yield _Session()

    return lifespan


def build_server(
    store: GraphStore, embedder: Embedder, settings: McpServerSettings
) -> MCPServer:
    """Return the evidence MCP server with its three read-only tools.

    The lifespan connects the store once, when the server starts. It does not
    close the store, because the caller owns the store and its connection pool.

    Args:
        store: The graph store to read. Each read uses
            ``settings.request_deadline_seconds`` as its timeout.
        embedder: Embeds queries for the semantic leg of a search. A search in
            lexical mode does not call it.
        settings: The trusted scope and the output limits.

    Returns:
        A server ready for ``run()`` or for an in-memory client.
    """
    scope = settings.scope
    deadline = settings.request_deadline_seconds

    server = MCPServer(
        name=_SERVER_NAME,
        instructions=(
            "Read-only access to the evidence passages of the configured "
            "documents. A score is not a confidence. A valid citation shows that "
            "the text was fetched, not that it supports a claim. No match is not "
            "proof that the passage does not exist."
        ),
        lifespan=_store_lifespan(store),
    )

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Find passages in the configured documents by keyword, meaning or "
            "both. Each hit has an evidence id for fetch_evidence. A score orders "
            "hits and is not a confidence. No hits does not prove that the "
            "documents lack the information. Semantic and hybrid modes need the "
            "same embedding model and backend that ingestion used. Dimension "
            "mismatches fail semantic mode and make hybrid mode return lexical "
            "hits only. Equal dimensions do not verify model identity."
        ),
    )
    async def search_evidence(
        ctx: Context[_Session, Any],
        query: str,
        mode: DiscoveryMode = DiscoveryMode.HYBRID,
        limit: Annotated[int, Field(ge=1)] | None = None,
    ) -> DiscoveryResult:
        """Find passages that match a query, best first.

        Args:
            ctx: The request context.
            query: The words to search for.
            mode: Which search legs run. The default runs both.
            limit: The most hits to return. Values above the configured maximum
                are capped, and the result is marked truncated.

        Returns:
            The hits and the status of the search. In hybrid mode, mismatched
            vector dimensions give lexical hits and a failed semantic leg.

        Raises:
            ToolError: The evidence store could not run the search, or the query
                embedder does not match the stored vectors in semantic mode.
        """
        requested = settings.max_hits if limit is None else limit
        effective = min(requested, settings.max_hits)
        dimension_mismatch = False
        if mode is not DiscoveryMode.LEXICAL:
            dimension_mismatch = await _dimensions_mismatch(
                store, embedder, deadline=deadline
            )
            if dimension_mismatch and mode is DiscoveryMode.SEMANTIC:
                raise ToolError(_EMBEDDING_MISMATCH)
        search_mode = DiscoveryMode.LEXICAL if dimension_mismatch else mode
        try:
            result = await discover(
                store,
                embedder,
                query,
                mode=search_mode,
                limit=effective,
                scope=scope,
                timeout=deadline,
            )
        except Exception:
            _LOGGER.exception("Evidence search failed")
            raise ToolError(_STORE_UNAVAILABLE) from None
        if result.status is DiscoveryStatus.FAILED:
            raise ToolError(_STORE_UNAVAILABLE)
        if dimension_mismatch:
            result = _with_semantic_failure(result)

        snippets_cut = False
        hits: list[DiscoveryHit] = []
        for hit in result.hits:
            if len(hit.snippet) > settings.max_snippet_chars:
                snippets_cut = True
                hits.append(
                    hit.model_copy(
                        update={"snippet": hit.snippet[: settings.max_snippet_chars]}
                    )
                )
            else:
                hits.append(hit)
        kept, dropped = _drop_to_budget(
            hits,
            lambda items: result.model_copy(update={"hits": items, "truncated": True}),
            settings.max_response_chars,
        )
        return result.model_copy(
            update={
                "hits": kept,
                "truncated": result.truncated
                or requested > settings.max_hits
                or snippets_cut
                or dropped,
            }
        )

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Return the exact text of evidence ids from search_evidence. The text "
            "is what the document says at that version. Ids outside the configured "
            "scope or missing from the store both return unavailable."
        ),
    )
    async def fetch_evidence(
        ctx: Context[_Session, Any],
        evidence_ids: list[str],
        max_chars: Annotated[int, Field(ge=1)] | None = None,
    ) -> FetchResult:
        """Return the text of each evidence id, in the order given.

        Args:
            ctx: The request context. Its lifespan state records the fetched ids.
            evidence_ids: Ids from search results or citations.
            max_chars: The most characters returned for each id. Values above
                the configured maximum are capped. Longer text is marked
                truncated.

        Returns:
            One outcome for each id that was not dropped to meet the size limit.

        Raises:
            ToolError: More ids were passed than the configured maximum.
        """
        _check_id_count(evidence_ids, settings.max_fetch_ids)
        cap = settings.max_fetch_chars
        if max_chars is not None:
            cap = min(max_chars, cap)
        outcomes = await fetch(
            store,
            evidence_ids,
            scope=scope,
            max_chars=cap,
            timeout=deadline,
        )
        if outcomes and all(o.status is FetchStatus.FAILED for o in outcomes):
            raise ToolError(_STORE_UNAVAILABLE)
        kept, dropped = _drop_to_budget(
            outcomes,
            lambda items: FetchResult(outcomes=items, truncated=True),
            settings.max_response_chars,
        )
        session = _session(ctx)
        session.fetched_ids.update(
            outcome.evidence_id
            for outcome in kept
            if outcome.status is FetchStatus.OK and not outcome.partial
        )
        return FetchResult(outcomes=kept, truncated=dropped)

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Check that cited evidence ids trace to text this server fetched in "
            "this session. A valid verdict shows traceability only. It does not "
            "show that the text supports the claim. not_fetched means the id was "
            "not fetched since the server started."
        ),
    )
    async def check_citations(
        ctx: Context[_Session, Any],
        cited_evidence_ids: list[str],
    ) -> CitationResult:
        """Return one verdict for each cited evidence id, in the order given.

        Args:
            ctx: The request context. Its lifespan state holds the fetched ids.
            cited_evidence_ids: The ids that an answer cites.

        Returns:
            One verdict for each cited id. The result is not cut to the size
            limit, because the id count limit bounds it.

        Raises:
            ToolError: More ids were passed than the configured maximum.
        """
        _check_id_count(cited_evidence_ids, settings.max_fetch_ids)
        session = _session(ctx)
        checks = await verify_citations(
            cited_evidence_ids, session.fetched_ids, scope=scope
        )
        kept, dropped = _drop_to_budget(
            checks,
            lambda items: CitationResult(checks=items, truncated=True),
            settings.max_response_chars,
        )
        return CitationResult(checks=kept, truncated=dropped)

    return server


async def _dimensions_mismatch(
    store: GraphStore, embedder: Embedder, *, deadline: float
) -> bool:
    """Detect incompatible dimensions, leaving absent indexes to discovery."""
    try:
        rows = await store.execute_read(
            *vector_index_dimensions_query(CHUNK_LABEL, _EMBEDDING_PROPERTY),
            timeout=deadline,
        )
    except Exception:
        _LOGGER.exception("Could not read the vector index dimension")
        raise ToolError(_STORE_UNAVAILABLE) from None
    if not rows:
        return False
    try:
        embedder_dimensions = await embedder.dimensions()
    except Exception:
        _LOGGER.exception("The query embedder could not report its dimensions")
        raise ToolError(_EMBEDDER_UNAVAILABLE) from None
    return rows[0]["dimensions"] != embedder_dimensions


def _with_semantic_failure(lexical: DiscoveryResult) -> DiscoveryResult:
    """Report a hybrid search that ran lexical only because of a mismatch.

    An ok or no-match lexical result becomes partial. Any other status keeps its
    meaning, and the failed semantic leg is added to the failures.
    """
    failure = LegFailure(leg=DiscoveryLeg.SEMANTIC, message=_EMBEDDING_MISMATCH)
    if lexical.status in (DiscoveryStatus.OK, DiscoveryStatus.NO_MATCH):
        status = DiscoveryStatus.PARTIAL
    else:
        status = lexical.status
    return lexical.model_copy(
        update={"status": status, "failures": [*lexical.failures, failure]}
    )


def _session(ctx: Context[_Session, Any]) -> _Session:
    """Return the session state of the current server process."""
    return ctx.request_context.lifespan_context


def _check_id_count(evidence_ids: Sequence[str], maximum: int) -> None:
    """Raise a correctable tool error when a call names too many ids."""
    if len(evidence_ids) > maximum:
        raise ToolError(f"at most {maximum} evidence ids per call")


def _drop_to_budget(
    items: Sequence[_ModelT],
    build: Callable[[list[_ModelT]], BaseModel],
    budget: int,
) -> tuple[list[_ModelT], bool]:
    """Drop trailing items until the built result fits the size budget.

    The size is the JSON length of the result counted twice, because the SDK
    sends the text copy and the structured copy.

    Args:
        items: The items in rank order, best first.
        build: Builds the result that holds a list of items.
        budget: The most characters the serialized result may take.

    Returns:
        The items that fit, and whether any item was dropped.
    """
    kept = list(items)
    dropped = False
    while kept and _serialized_size(build(kept)) > budget:
        kept.pop()
        dropped = True
    if _serialized_size(build(kept)) > budget:
        raise ToolError("max_response_chars is too small for an empty result")
    return kept, dropped


def _serialized_size(model: BaseModel) -> int:
    """Return the size of a result as the SDK sends it, text and structured copies."""
    return 2 * len(model.model_dump_json())


async def serve_stdio(server: MCPServer, store: GraphStore) -> None:
    """Serve over stdio, then close the store in the same event loop.

    The store opens its driver inside the server's event loop, so it has to
    close in that loop too.

    Args:
        server: The server to run. Its lifespan connects the store.
        store: The graph store that the server reads.
    """
    try:
        await server.run_stdio_async()
    finally:
        await store.close()
