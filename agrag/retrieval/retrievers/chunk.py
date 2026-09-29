"""Chunk retriever: dense vector search over chunks."""

from collections.abc import Mapping
from typing import Any, cast

from opentelemetry.trace import SpanKind, Tracer

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import hydrate_chunks_by_id_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer, record_swallowed_exception
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_chunks, record_results, retrieval_span
from agrag.vectordb.base import VectorStore


class ChunkRetriever(Retriever):
    """Dense chunk search via vector similarity.

    Chunks are never tombstoned, so no merged_into resolution is
    needed. Embeds the query, searches via the GraphStore-native or
    VectorStore path, then hydrates each hit into a Chunk. The native
    path searches the ``Chunk`` vector index ingestion provisions; the
    VectorStore path searches ``chunk_collection``.
    """

    name = "chunk"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Construct a ChunkRetriever.

        Args:
            graph_store: Backs chunk search when vector_store is
                absent.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration; defaults from
                environment.
            tracer: Opens the retriever and its children's spans. None
                opens no recorded span.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()
        self._tracer = tracer

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run chunk search and return hydrated results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.chunk_top_k.
                Zero or negative returns no results without searching.

        Returns:
            Ranked SearchResults with hydrated Chunk items. A child chunk result
            carries its parent chunk in ``SearchResult.parent``.
        """
        effective_limit = limit if limit is not None else self._settings.chunk_top_k
        with retrieval_span(
            self._tracer,
            "agrag.retrieval.chunk",
            query=query,
            filters=filters,
            attributes={"agrag.limit": effective_limit},
        ) as span:
            if effective_limit <= 0:
                record_results(span, [])
                return []
            hits = await vector_search(
                query,
                embedder=self._embedder,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                collection=self._settings.chunk_collection,
                labels=[CHUNK_LABEL],
                limit=effective_limit,
                filters=filters,
                settings=self._settings,
                tracer=self._tracer,
            )
            if not hits:
                record_results(span, [])
                return []
            ids = [str(h.id) for h in hits]
            with get_tracer(self._tracer).start_as_current_span(
                "agrag.retrieval.hydrate_chunks",
                attributes={"agrag.requested_count": len(hits)},
            ) as hydrate:
                try:
                    rows = await self._graph_store.execute_read(
                        hydrate_chunks_by_id_query(), {"ids": ids, "job_id": None}
                    )
                except Exception as exc:  # noqa: BLE001
                    record_swallowed_exception(exc)
                    record_results(span, [])
                    return []
                by_id: dict[str, Chunk] = {}
                for row in rows:
                    try:
                        node = (
                            row.get("n")
                            if isinstance(row, dict) and "n" in row
                            else row
                        )
                        chunk = self._parse_chunk_node(node)
                        if chunk is not None:
                            by_id[str(chunk.id)] = chunk
                    except Exception:
                        continue
                if hydrate.is_recording():
                    hydrate.set_attribute("agrag.hydrated_count", len(by_id))
            parents = await self._hydrate_parents(list(by_id.values()))
            results: list[SearchResult] = []
            for hit in hits:
                try:
                    chunk = by_id.get(str(hit.id))
                    if chunk is None:
                        continue
                    parent = parents.get(str(chunk.parent_id))
                    if chunk.parent_id is not None and parent is None:
                        continue
                    results.append(
                        SearchResult(
                            item=chunk,
                            score=hit.score,
                            method=self.name,
                            parent=parent,
                        )
                    )
                except Exception:
                    continue
            record_results(span, results)
            return results

    async def _hydrate_parents(self, chunks: list[Chunk]) -> dict[str, Chunk]:
        """Load the distinct parents of child chunks with one query.

        A parent that is missing or closed is left out, so its child cannot become a
        result. A failed query returns no parents.
        """
        parent_ids = sorted({str(c.parent_id) for c in chunks if c.parent_id})
        if not parent_ids:
            return {}
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.retrieval.hydrate_parents",
            kind=SpanKind.INTERNAL,
            attributes={"agrag.parent_count": len(parent_ids)},
        ) as span:
            try:
                rows = await self._graph_store.execute_read(
                    hydrate_chunks_by_id_query(), {"ids": parent_ids, "job_id": None}
                )
            except Exception as exc:
                record_swallowed_exception(exc)
                return {}
            parents: dict[str, Chunk] = {}
            for row in rows:
                node = row.get("n") if isinstance(row, dict) and "n" in row else row
                parent = self._parse_chunk_node(node)
                if parent is not None:
                    parents[str(parent.id)] = parent
            record_chunks(span, list(parents.values()))
        return parents

    @staticmethod
    def _parse_chunk_node(node: object) -> Chunk | None:
        """Parse a GraphStore node row into a Chunk."""
        try:
            props: dict = {}
            node_id: object = None

            if isinstance(node, dict) and "properties" in node:
                props = dict(node.get("properties") or {})
                node_id = node.get("id") or props.get("id")
            elif isinstance(node, dict) and "id" in node:
                props = dict(node)
                node_id = props.get("id")
            else:
                if not hasattr(node, "keys"):
                    return None
                props = dict(cast(Mapping[str, Any], node))
                node_id = props.get("id")

            if node_id is None:
                return None

            import json  # noqa: PLC0415
            from uuid import UUID  # noqa: PLC0415

            from agrag.common.data_models.provenance import (  # noqa: PLC0415
                PageProvenance,
                TextProvenance,
            )

            prov_raw = props.get("provenance")
            prov_data: dict[str, Any]
            if isinstance(prov_raw, str):
                prov_data = json.loads(prov_raw)
            elif isinstance(prov_raw, dict):
                prov_data = prov_raw
            else:
                prov_data = {"kind": "text", "char_start": 0, "char_end": 0}

            if prov_data.get("kind") == "page":
                provenance = PageProvenance(**prov_data)
            else:
                provenance = TextProvenance(**prov_data)

            embedding = props.get("embedding")

            chunk = Chunk(
                id=UUID(str(node_id)),
                document_id=UUID(props["document_id"]),
                index=props.get("index", 0),
                text=props.get("text", ""),
                provenance=provenance,
                heading_path=props.get("heading_path", []),
                content_kind=props.get("content_kind", "text"),
                chunker=props.get("chunker"),
                chunker_hash=props.get("chunker_hash"),
                level=props.get("level", 0),
                parent_id=UUID(str(props["parent_id"]))
                if props.get("parent_id")
                else None,
            )
            if embedding is not None:
                chunk.embedding = list(embedding)
            return chunk
        except Exception:
            return None
