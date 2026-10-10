"""Tests for EntityRetriever in agrag.retrieval.retrievers.entity.

Patches ``agrag.retrieval.retrievers.entity.vector_search`` with AsyncMock,
using an AsyncMock graph store that answers loading reads and a minimal
MockEmbedder. Covers loading hits from the graph, dropping hits the graph
cannot load, document scoping, and resolved-entity search.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.entities import load_entities_by_id_query
from agrag.cypher.resolution_read import fetch_active_resolved_member_ids_query
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.retrievers.entity import EntityRetriever


class MockEmbedder:
    """Mock embedder for entity retriever tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Method under test."""
        return [[0.1, 0.2] for _ in texts]


def _graph_store(
    entities: tuple[Entity, ...] = (),
    allowed_ids: tuple = (),
    superseded_ids: tuple = (),
) -> AsyncMock:
    """Return a graph store that loads ``entities`` and scopes to ``allowed_ids``.

    ``superseded_ids`` are raw ids an active resolved entity replaces.
    """
    load_query = load_entities_by_id_query()

    async def execute_read(query: str, params: dict) -> list[dict]:
        """Answer the scope, loading, and supersession reads."""
        if "document_ids" in params:
            return [{"id": str(item_id)} for item_id in allowed_ids]
        if query == load_query:
            return [
                {
                    "n": {
                        "id": str(entity.id),
                        "name": entity.name,
                        "merge_key": entity.merge_key,
                    }
                }
                for entity in entities
                if str(entity.id) in params["ids"]
            ]
        return [
            {"entity_id": str(item_id)}
            for item_id in superseded_ids
            if str(item_id) in params["ids"]
        ]

    store = AsyncMock()
    store.execute_read.side_effect = execute_read
    return store


class TestEntityRetriever:
    """EntityRetriever loads hits from the graph."""

    async def test_document_scope_keeps_resolved_entity_with_scoped_member(
        self,
    ) -> None:
        """Document scope filters resolved entities by their member evidence."""
        scoped_member_id = uuid4()
        resolved = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            member_ids=[scoped_member_id],
        )
        outside_scope = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Grace Hopper",
            member_ids=[uuid4()],
        )
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [{"id": str(scoped_member_id)}]

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [],
                    [
                        VectorHit(id=resolved.id, score=0.9, payload={}),
                        VectorHit(id=outside_scope.id, score=0.8, payload={}),
                    ],
                ],
            ) as vector_search_mock,
            patch(
                "agrag.retrieval.retrievers.entity.load_resolved_entities",
                new_callable=AsyncMock,
                return_value={
                    resolved.id: resolved,
                    outside_scope.id: outside_scope,
                },
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"])
            )

        assert [result.item for result in results] == [resolved]
        resolved_filters = vector_search_mock.await_args_list[1].kwargs["filters"]
        assert resolved_filters.document_ids == []

    async def test_document_scope_expands_raw_search_for_in_scope_entity(
        self,
    ) -> None:
        """Document scope expands past higher-ranked entities from other documents."""
        scoped_id = uuid4()
        scoped = Entity(id=scoped_id, label="Person", name="Ada")
        graph_store = _graph_store(entities=(scoped,), allowed_ids=(scoped_id,))
        outside_first = VectorHit(id=uuid4(), score=0.99, payload={})
        outside_second = VectorHit(id=uuid4(), score=0.98, payload={})

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [outside_first, outside_second],
                    [
                        outside_first,
                        outside_second,
                        VectorHit(id=scoped_id, score=0.8, payload={}),
                    ],
                    [],
                ],
            ) as vector_search_mock,
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item.id for result in results] == [scoped.id]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 4, 2]
        assert all(
            call.kwargs["filters"].document_ids == []
            for call in vector_search_mock.await_args_list
        )

    async def test_document_scope_backfills_past_resolved_raw_members(self) -> None:
        """Document scope does not count raw members an active result replaces."""
        first_member_id = uuid4()
        second_member_id = uuid4()
        regular_id = uuid4()
        regular = Entity(id=regular_id, label="Person", name="Katherine")
        graph_store = _graph_store(
            entities=(regular,),
            allowed_ids=(first_member_id, second_member_id, regular_id),
            superseded_ids=(first_member_id, second_member_id),
        )
        first_member = VectorHit(id=first_member_id, score=0.99, payload={})
        second_member = VectorHit(id=second_member_id, score=0.98, payload={})
        regular_hit = VectorHit(id=regular_id, score=0.8, payload={})

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [first_member, second_member],
                    [first_member, second_member, regular_hit],
                    [],
                ],
            ) as vector_search_mock,
            patch(
                "agrag.retrieval.retrievers.entity.load_resolved_entities",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item.id for result in results] == [regular.id]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 4, 2]

    async def test_document_scope_raises_when_raw_backfill_fails(self) -> None:
        """A failed raw backfill raises instead of returning a partial list."""
        scoped_id = uuid4()
        scoped = Entity(id=scoped_id, label="Person", name="Ada")
        graph_store = _graph_store(entities=(scoped,), allowed_ids=(scoped_id,))
        outside = VectorHit(id=uuid4(), score=0.99, payload={})

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [outside, VectorHit(id=scoped_id, score=0.8, payload={})],
                    RuntimeError("temporary vector failure"),
                ],
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            with pytest.raises(RuntimeError, match="temporary vector failure"):
                await retriever.retrieve(
                    "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
                )

    async def test_document_scope_expands_resolved_search_for_in_scope_member(
        self,
    ) -> None:
        """Resolved search expands past higher-ranked entities outside the scope."""
        scoped_member_id = uuid4()
        scoped = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            member_ids=[scoped_member_id],
        )
        outside_first = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Grace Hopper",
            member_ids=[uuid4()],
        )
        outside_second = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Katherine Johnson",
            member_ids=[uuid4()],
        )
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [{"id": str(scoped_member_id)}]

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [],
                    [
                        VectorHit(id=outside_first.id, score=0.99, payload={}),
                        VectorHit(id=outside_second.id, score=0.98, payload={}),
                    ],
                    [
                        VectorHit(id=outside_first.id, score=0.99, payload={}),
                        VectorHit(id=outside_second.id, score=0.98, payload={}),
                        VectorHit(id=scoped.id, score=0.8, payload={}),
                    ],
                ],
            ) as vector_search_mock,
            patch(
                "agrag.retrieval.retrievers.entity.load_resolved_entities",
                new_callable=AsyncMock,
                side_effect=[
                    {
                        outside_first.id: outside_first,
                        outside_second.id: outside_second,
                    },
                    {
                        outside_first.id: outside_first,
                        outside_second.id: outside_second,
                        scoped.id: scoped,
                    },
                ],
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item.id for result in results] == [scoped.id]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 2, 4]
        assert all(
            call.kwargs["filters"].document_ids == []
            for call in vector_search_mock.await_args_list
        )

    async def test_document_scope_raises_when_resolved_backfill_fails(self) -> None:
        """A failed resolved backfill raises instead of returning a partial list."""
        scoped_member_id = uuid4()
        scoped = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            member_ids=[scoped_member_id],
        )
        outside = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Grace Hopper",
            member_ids=[uuid4()],
        )
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [{"id": str(scoped_member_id)}]

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [],
                    [
                        VectorHit(id=outside.id, score=0.99, payload={}),
                        VectorHit(id=scoped.id, score=0.8, payload={}),
                    ],
                    RuntimeError("temporary vector failure"),
                ],
            ) as vector_search_mock,
            patch(
                "agrag.retrieval.retrievers.entity.load_resolved_entities",
                new_callable=AsyncMock,
                return_value={outside.id: outside, scoped.id: scoped},
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            with pytest.raises(RuntimeError, match="temporary vector failure"):
                await retriever.retrieve(
                    "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
                )

        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 2, 4]

    async def test_drops_hits_the_graph_cannot_load(self) -> None:
        """A hit with no matching graph node is dropped; the others stay."""
        live = Entity(id=uuid4(), label="Person", name="Alice")
        gs = _graph_store(entities=(live,))

        with patch(
            "agrag.retrieval.retrievers.entity.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [
                VectorHit(id=uuid4(), score=0.95, payload={}),
                VectorHit(id=live.id, score=0.9, payload={}),
            ]

            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            results = await retriever.retrieve("test query")

        assert [result.item.id for result in results] == [live.id]

    async def test_zero_limit_returns_empty_without_searching(self) -> None:
        """limit=0 returns no results and never reaches vector_search."""
        gs = AsyncMock()
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query", limit=0)

            assert results == []
            mock_vs.assert_not_called()
            gs.execute_read.assert_not_called()

    async def test_negative_limit_returns_empty_without_searching(self) -> None:
        """A negative limit returns no results and never reaches vector_search."""
        gs = AsyncMock()
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query", limit=-2)

            assert results == []
            mock_vs.assert_not_called()
            gs.execute_read.assert_not_called()

    async def test_searches_resolved_collection_when_raw_hits_are_empty(self) -> None:
        """No raw hits still lets the resolved-entity collection be searched."""
        resolved = ResolvedEntity(
            id=uuid4(), label="Person", name="Ada Lovelace", member_ids=[uuid4()]
        )
        gs = AsyncMock()
        gs.execute_read.return_value = []

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[[], [VectorHit(id=resolved.id, score=0.8, payload={})]],
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.load_resolved_entities",
                new_callable=AsyncMock,
                return_value={resolved.id: resolved},
            ),
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            results = await retriever.retrieve("Ada")

        assert [result.item for result in results] == [resolved]
        assert mock_vs.await_count == 2

    async def test_resolved_collection_search_failure_raises(self) -> None:
        """A resolved-collection search failure raises, not a raw-only list."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = _graph_store(entities=(ent,))

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [VectorHit(id=ent.id, score=0.9, payload={})],
                    RuntimeError("collection not found"),
                ],
            ),
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            with pytest.raises(RuntimeError, match="collection not found"):
                await retriever.retrieve("Alice")

    async def test_loading_read_failure_raises(self) -> None:
        """A failed entity load raises, so it is not read as no results."""
        gs = AsyncMock()
        gs.execute_read.side_effect = RuntimeError("db down")

        with patch(
            "agrag.retrieval.retrievers.entity.vector_search",
            new_callable=AsyncMock,
            return_value=[VectorHit(id=uuid4(), score=0.9, payload={})],
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            with pytest.raises(RuntimeError, match="db down"):
                await retriever.retrieve("Alice")

    async def test_supersession_read_failure_raises(self) -> None:
        """A failed resolved-member read raises instead of keeping raw members."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = _graph_store(entities=(ent,))
        base_read = gs.execute_read.side_effect

        async def execute_read(query: str, params: dict) -> list[dict]:
            if query == fetch_active_resolved_member_ids_query():
                raise RuntimeError("db down")
            return await base_read(query, params)

        gs.execute_read.side_effect = execute_read

        with patch(
            "agrag.retrieval.retrievers.entity.vector_search",
            new_callable=AsyncMock,
            return_value=[VectorHit(id=ent.id, score=0.9, payload={})],
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            with pytest.raises(RuntimeError, match="db down"):
                await retriever.retrieve("Alice")
