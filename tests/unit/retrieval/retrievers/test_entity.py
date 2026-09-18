"""Tests for EntityRetriever in agrag.retrieval.retrievers.entity.

Patches ``agrag.retrieval.retrievers.entity.vector_search`` and
``resolve_entity`` with AsyncMock, using an AsyncMock graph store and a
minimal MockEmbedder. Covers returning entities resolved through
resolve_entity, skipping hits that fail to resolve (ValueError), and a
regression proving the retriever returns the live survivor entity rather
than a tombstoned id when the vector store's hit has since been merged.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorHit
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


class TestEntityRetriever:
    """EntityRetriever resolves hits through merged_into."""

    async def test_returns_resolved_entities(self) -> None:
        """Hits are resolved through resolve_entity and returned."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == ent.id
            assert results[0].method == "entity"

    async def test_returns_materialization_without_its_raw_member(self) -> None:
        """An active resolved entity replaces its member in user-facing search."""
        raw = Entity(id=uuid4(), label="Person", name="Ada")
        resolved = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            member_ids=[raw.id, uuid4()],
        )
        graph_store = AsyncMock()
        graph_store.execute_read.side_effect = [
            [],
            [{"entity_id": str(raw.id)}],
        ]

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [VectorHit(id=raw.id, score=0.9, payload={})],
                    [VectorHit(id=resolved.id, score=0.8, payload={})],
                ],
            ),
            patch(
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
                new_callable=AsyncMock,
                return_value={resolved.id: resolved},
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve("Ada")

        assert [result.item for result in results] == [resolved]

    async def test_skips_unresolvable_entities(self) -> None:
        """Entities that fail to resolve are skipped."""
        gs = AsyncMock()
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]
            mock_resolve.side_effect = ValueError("not found")

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 0

    async def test_regression_returns_survivor_not_tombstone(
        self,
    ) -> None:
        """Regression: EntityRetriever returns survivor, not tombstone.

        When the store has a merged_into chain, the retriever must
        return the live survivor entity. This test fails without
        resolve_entity wired in correctly.
        """
        survivor = Entity(id=uuid4(), label="Person", name="Alice (survivor)")
        tombstone_id = uuid4()

        gs = AsyncMock()
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            # The vector store returns the tombstone id.
            mock_vs.return_value = [VectorHit(id=tombstone_id, score=0.9, payload={})]
            # resolve_entity follows merged_into and returns survivor.
            mock_resolve.return_value = survivor

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == survivor.id
            assert results[0].item.name == "Alice (survivor)"

    async def test_hydrated_entity_skips_resolve_entity_round_trip(self) -> None:
        """A row that hydrates directly avoids the per-hit resolve_entity call.

        This is exactly what the diff's batch-hydration change is for: when
        the hydration query already returns a live entity for a hit's id,
        the retriever must not fall back to resolve_entity for it.
        """
        eid = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "n": {
                    "id": str(eid),
                    "name": "Alice",
                    "merge_key": "Person:alice",
                    "merged_from": [],
                    "merge_count": 1,
                    "source_chunk_ids": [],
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "labels": ["Person"],
                }
            }
        ]
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=eid, score=0.9, payload={})]

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.name == "Alice"
            mock_resolve.assert_not_called()

    async def test_unwrappable_row_falls_through_to_resolve_entity(self) -> None:
        """A row whose 'n' value parses to nothing is skipped, not fatal.

        _parse_entity_node's own {"n": ...} unwrapping means retrying the
        raw row after the wrapped node fails still yields None here, so the
        hit falls through to per-hit resolve_entity instead of being dropped.
        """
        eid = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [{"n": {}}]
        ent = Entity(id=eid, label="Person", name="Alice")
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=eid, score=0.9, payload={})]
            mock_resolve.return_value = ent

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == eid
            mock_resolve.assert_awaited_once()

    async def test_hydration_query_failure_falls_back_to_resolve_entity(self) -> None:
        """A hydration query error still lets resolve_entity find the entity."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        gs.execute_read.side_effect = RuntimeError("db down")
        embedder = MockEmbedder()

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == ent.id
            mock_resolve.assert_awaited_once()

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
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
                new_callable=AsyncMock,
                return_value={resolved.id: resolved},
            ),
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            results = await retriever.retrieve("Ada")

        assert [result.item for result in results] == [resolved]
        assert mock_vs.await_count == 2

    async def test_resolved_search_uses_property_label_filter(self) -> None:
        """A domain label filter reaches resolved search as a property filter."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        filters = SearchFilters(labels=["Person"])

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[[], []],
            ) as mock_vs,
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            await retriever.retrieve("Ada", filters=filters)

        raw_call, resolved_call = mock_vs.call_args_list
        assert raw_call.kwargs["filters"].labels == ["Person"]
        resolved_filters = resolved_call.kwargs["filters"]
        assert resolved_filters.labels == []
        assert resolved_filters.properties["label"] == ["Person"]

    async def test_missing_resolved_collection_falls_back_to_raw_results(
        self,
    ) -> None:
        """A resolved-collection search failure keeps the raw results."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        gs.execute_read.return_value = []

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [VectorHit(id=ent.id, score=0.9, payload={})],
                    RuntimeError("collection not found"),
                ],
            ),
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
                return_value=ent,
            ),
        ):
            retriever = EntityRetriever(graph_store=gs, embedder=MockEmbedder())
            results = await retriever.retrieve("Alice")

        assert [result.item for result in results] == [ent]
