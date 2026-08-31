"""Chunk retriever: dense vector search over chunks."""

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class ChunkRetriever(Retriever):
    """Dense chunk search via vector similarity.

    Chunks are never tombstoned, so no merged_into resolution is
    needed. Embeds the query, searches via the GraphStore-native or
    VectorStore path, then hydrates each hit into a Chunk.
    """

    name = "chunk"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a ChunkRetriever.

        Args:
            graph_store: Backs chunk search when vector_store is
                absent.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()

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

        Returns:
            Ranked SearchResults with hydrated Chunk items.
        """
        effective_limit = limit or self._settings.chunk_top_k
        label = self._settings.chunk_collection
        hits = await vector_search(
            query,
            embedder=self._embedder,
            graph_store=self._graph_store,
            vector_store=self._vector_store,
            label_or_collection=label,
            limit=effective_limit,
            filters=filters,
            settings=self._settings,
        )
        results: list[SearchResult] = []
        for hit in hits:
            try:
                rows = await self._graph_store.execute_read(
                    f"MATCH (n:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
                    f"{{id: $id}}) RETURN n",
                    {"id": str(hit.id)},
                )
                if not rows:
                    continue
                node = (
                    rows[0].get("n")
                    if isinstance(rows[0], dict) and "n" in rows[0]
                    else rows[0]
                )
                chunk = self._parse_chunk_node(node)
                if chunk is not None:
                    results.append(
                        SearchResult(
                            item=chunk,
                            score=hit.score,
                            method=self.name,
                        )
                    )
            except Exception:
                continue
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
                try:
                    props = dict(node)  # type: ignore[arg-type]
                except Exception:
                    return None
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
            )
            if embedding is not None:
                chunk.embedding = list(embedding)
            return chunk
        except Exception:
            return None
