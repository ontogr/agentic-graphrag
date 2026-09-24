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
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
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
        graph_store = AsyncMock()
        graph_store.execute_read.side_effect = [
            [{"id": str(scoped_id)}],
            [],
            [],
        ]
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
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
                return_value=scoped,
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item for result in results] == [scoped]
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
        graph_store = AsyncMock()
        graph_store.execute_read.side_effect = [
            [
                {"id": str(first_member_id)},
                {"id": str(second_member_id)},
                {"id": str(regular_id)},
            ],
            [{"entity_id": str(first_member_id)}],
            [
                {"entity_id": str(first_member_id)},
                {"entity_id": str(second_member_id)},
            ],
            [],
        ]
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
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
                return_value=regular,
            ),
            patch(
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
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

        assert [result.item for result in results] == [regular]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 4, 2]

    async def test_document_scope_keeps_raw_results_when_backfill_fails(
        self,
    ) -> None:
        """A failed raw backfill keeps the scoped result from the first search."""
        scoped_id = uuid4()
        scoped = Entity(id=scoped_id, label="Person", name="Ada")
        graph_store = AsyncMock()
        graph_store.execute_read.side_effect = [
            [{"id": str(scoped_id)}],
            [],
            [],
        ]
        outside = VectorHit(id=uuid4(), score=0.99, payload={})

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=[
                    [outside, VectorHit(id=scoped_id, score=0.8, payload={})],
                    RuntimeError("temporary vector failure"),
                    [],
                ],
            ) as vector_search_mock,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
                return_value=scoped,
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item for result in results] == [scoped]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 4, 2]

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
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
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

        assert [result.item for result in results] == [scoped]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 2, 4]
        assert all(
            call.kwargs["filters"].document_ids == []
            for call in vector_search_mock.await_args_list
        )

    async def test_document_scope_keeps_resolved_results_when_backfill_fails(
        self,
    ) -> None:
        """A failed resolved backfill keeps the scoped result from the first search."""
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
                "agrag.retrieval.retrievers.entity.hydrate_resolved_entities",
                new_callable=AsyncMock,
                return_value={outside.id: outside, scoped.id: scoped},
            ),
        ):
            retriever = EntityRetriever(
                graph_store=graph_store, embedder=MockEmbedder()
            )
            results = await retriever.retrieve(
                "Ada", filters=SearchFilters(document_ids=["doc-1"]), limit=2
            )

        assert [result.item for result in results] == [scoped]
        limits = [call.kwargs["limit"] for call in vector_search_mock.await_args_list]
        assert limits == [2, 2, 4]

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
