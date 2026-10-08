"""Chunk retriever: dense vector search over chunks."""

from collections.abc import Mapping
from typing import Any, cast

from opentelemetry.trace import Tracer

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import load_chunks_by_id_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_results, retrieval_span
from agrag.vectordb.base import VectorStore


class ChunkRetriever(Retriever):
    """Dense chunk search via vector similarity.

    Embeds the query, searches via the GraphStore-native or VectorStore
    path, then loads each hit into a Chunk. The native
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
            settings: Retrieval configuration. Defaults from
                environment.
            tracer: Opens spans for the retriever and its children. None
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
        """Run chunk search and return loaded results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.chunk_top_k.
                Zero or negative returns no results without searching.

        Returns:
            Ranked SearchResults with loaded Chunk items. The list is empty when
                the limit is not positive, or when the search ran and found
                nothing.

        Raises:
            Exception: Any embedding, vector search, or graph read
                failure propagates, so a failed search is not mistaken
                for an empty one.
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
                "agrag.retrieval.load_chunks",
                attributes={"agrag.requested_count": len(hits)},
            ) as load:
                rows = await self._graph_store.execute_read(
                    load_chunks_by_id_query(), {"ids": ids, "job_id": None}
                )
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
                if load.is_recording():
                    load.set_attribute("agrag.loaded_count", len(by_id))
            results: list[SearchResult] = []
            for hit in hits:
                try:
                    chunk = by_id.get(str(hit.id))
                    if chunk is None:
                        continue
                    results.append(
                        SearchResult(item=chunk, score=hit.score, method=self.name)
                    )
                except Exception:
                    continue
            record_results(span, results)
            return results

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
                section_ids=[UUID(str(i)) for i in props.get("section_ids", [])],
            )
            if embedding is not None:
                chunk.embedding = list(embedding)
            return chunk
        except Exception:
            return None
