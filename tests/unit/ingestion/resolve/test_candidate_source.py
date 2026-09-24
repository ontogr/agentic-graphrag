"""Tests for GraphCandidateSource and exact_match_lookup.

Covers same-label in-batch blocking with exact index sets, the guarantee
that the in-batch path never touches GraphStore.vector_search or
VectorStore.hybrid_search, batch-bounded cost independent of graph size,
both global_candidates_for routing branches, and exact_match_lookup alias
and tombstone-chain behavior.

Also covers the VectorStore-backed candidate path, which must hydrate the
persisted Entity by id rather than reconstructing its name from the display
text, and the neighbor-context builders LLMVerify's batched verification
reads: ``build_relation_neighbors`` from a batch's own extraction, and
``fetch_persisted_neighbors`` from the persisted graph.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import (
    MAX_NEIGHBORS_PER_ENTITY,
    GraphCandidateSource,
    build_relation_neighbors,
    exact_match_lookup,
    fetch_persisted_neighbors,
)


class MockEmbedder:
    """Mock embedder for candidate-source tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Method under test."""
        return [[0.1, 0.2] for _ in texts]


def _mention(text: str, label: str = "Show") -> ExtractedEntity:
    """Build a mention for candidate-source tests."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _relation(
    source_index: int, target_index: int, label: str = "WORKS_AT"
) -> ExtractedRelation:
    """Build a relation mention for the neighbor-builder tests."""
    return ExtractedRelation(
        chunk_id=uuid4(),
        label=label,
        source_index=source_index,
        target_index=target_index,
    )


def _source(
    *,
    vector_store: AsyncMock | None = None,
    top_k: int = 50,
) -> tuple[GraphCandidateSource, AsyncMock]:
    """Build a source with mocked stores for in-batch tests."""
    graph_store = AsyncMock()
    graph_store.vector_search = AsyncMock()
    source = GraphCandidateSource(
        graph_store=graph_store,
        embedder=MagicMock(),
        vector_store=vector_store,
        top_k=top_k,
    )
    return source, graph_store


class TestGraphCandidateSourceInBatch:
    """candidates_for blocks by label within the batch."""

    async def test_never_proposes_cross_label(self) -> None:
        """Only the same-label mention is proposed."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Apple", label="Organization"),
            _mention("Charles", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [2]

    async def test_proposes_all_same_label(self) -> None:
        """Every other same-label mention is proposed in order."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
            _mention("Grace", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [1, 2]
        assert await source.candidates_for(1, entities) == [0, 2]

    async def test_excludes_self(self) -> None:
        """A lone mention has no candidates."""
        source, _ = _source()
        assert await source.candidates_for(0, [_mention("Ada")]) == []


class TestInBatchNeverTouchesStores:
    """The in-batch path is pure and never searches a store."""

    async def test_never_calls_vector_search_or_hybrid_search(self) -> None:
        """Neither GraphStore nor VectorStore search runs in-batch."""
        vector_store = AsyncMock()
        vector_store.hybrid_search = AsyncMock()
        source, graph_store = _source(vector_store=vector_store)
        entities = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [1]
        graph_store.vector_search.assert_not_called()
        vector_store.hybrid_search.assert_not_called()
        graph_store.execute_read.assert_not_called()

    async def test_cost_bounded_by_batch_not_graph_size(self) -> None:
        """Same batch against small and huge graphs makes identical calls."""
        batch = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
            _mention("Acme", label="Organization"),
        ]
        small_source, small_store = _source()
        huge_vector_store = AsyncMock()
        huge_vector_store.hybrid_search = AsyncMock()
        huge_source, huge_store = _source(vector_store=huge_vector_store)
        small_results = [await small_source.candidates_for(i, batch) for i in range(3)]
        huge_results = [await huge_source.candidates_for(i, batch) for i in range(3)]
        assert small_results == huge_results == [[1], [0], []]
        assert small_store.method_calls == huge_store.method_calls == []
        small_store.vector_search.assert_not_called()
        huge_store.vector_search.assert_not_called()
        huge_vector_store.hybrid_search.assert_not_called()


class TestGraphCandidateSourceGlobalCandidatesFor:
    """global_candidates_for resolves vector hits into persisted entities."""

    async def test_returns_untruncated_name_for_vector_store_hit(self) -> None:
        """A colon in the real name is not truncated by the VectorStore path.

        Regression: the payload only carries embedding_text under "text", so
        guessing the name by splitting on ":" turned "Star Trek: Voyager"
        into "Star Trek". The fix hydrates the real node by id instead.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(entity_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Star Trek: Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert len(candidates) == 1
        assert candidates[0][0].name == "Star Trek: Voyager"
        assert candidates[0][1] == 0.9

    async def test_skips_hits_that_fail_to_hydrate(self) -> None:
        """A hit whose node cannot be hydrated is dropped, not guessed."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert candidates == []

    async def test_native_path_validates_payload_directly(self) -> None:
        """With no VectorStore, the native payload already has the real name.

        The native path must not be touched by the hydrate-by-id fix, and
        must not issue a graph read to get the name.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MockEmbedder(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"name": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        graph_store.execute_read.assert_not_called()
        assert len(candidates) == 1
        assert candidates[0][0].name == "Star Trek: Voyager"
        assert candidates[0][1] == 0.9

    async def test_returns_empty_when_no_hits(self) -> None:
        """No vector hits means no candidates on either branch."""
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MockEmbedder(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[],
        ):
            assert await source.global_candidates_for(_mention("Ada")) == []

        graph_store.execute_read.assert_not_called()

    async def test_hydration_keeps_each_score_with_its_own_entity(self) -> None:
        """Dropping an unhydrated hit does not shift scores onto other entities.

        Regression guard: associating scores with entities by position would
        give the surviving entity the dropped hit's score instead of its own.
        """
        dropped_id, kept_id = uuid4(), uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(kept_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(id=dropped_id, score=0.2, payload={"text": "Dropped"}),
                VectorHit(id=kept_id, score=0.95, payload={"text": "Voyager"}),
            ],
        ):
            candidates = await source.global_candidates_for(_mention("Voyager"))

        assert [entity.id for entity, _ in candidates] == [kept_id]
        assert [score for _, score in candidates] == [0.95]

    async def test_native_payload_mismatch_keeps_each_score_with_its_entity(
        self,
    ) -> None:
        """A label-mismatched native hit's score is not shifted onto the next."""
        source = GraphCandidateSource(
            graph_store=AsyncMock(), embedder=MockEmbedder(), vector_store=None
        )
        kept_id = uuid4()

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.1,
                    payload={"label": "Place", "name": "Paris"},
                ),
                VectorHit(
                    id=kept_id,
                    score=0.88,
                    payload={"label": "Show", "name": "Voyager"},
                ),
            ],
        ):
            candidates = await source.global_candidates_for(_mention("Voyager"))

        assert [entity.id for entity, _ in candidates] == [kept_id]
        assert [score for _, score in candidates] == [0.88]


class TestExactMatchLookup:
    """exact_match_lookup mirrors _global_exact_match behavior."""

    async def test_empty_returns_empty(self) -> None:
        """Empty mentions returns empty."""
        store = AsyncMock()
        result = await exact_match_lookup([], graph_store=store)
        assert result == {}
        store.execute_read.assert_not_called()

    async def test_groups_by_label_and_dedups(self) -> None:
        """One query per distinct label, deduped keys."""
        store = AsyncMock()
        cid = uuid4()
        m1 = ExtractedEntity(
            chunk_id=cid, label="Person", text="Alice", char_start=0, char_end=5
        )
        m2 = ExtractedEntity(
            chunk_id=cid, label="Person", text="alice", char_start=6, char_end=11
        )
        m3 = ExtractedEntity(
            chunk_id=cid, label="Organization", text="Acme", char_start=0, char_end=4
        )
        eid = uuid4()
        store.execute_read.side_effect = [
            [
                {
                    "n": {
                        "id": str(eid),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Alice",
                            "merge_key": "Person:alice",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ],
            [],
        ]
        result = await exact_match_lookup([m1, m2, m3], graph_store=store)
        assert result[0].id == eid
        assert result[1].id == eid
        assert 2 not in result
        assert store.execute_read.call_count == 2

    async def test_handles_flat_row_and_missing(self) -> None:
        """Handles flat row form and skips unparsable rows."""
        store = AsyncMock()
        cid = uuid4()
        entity_id = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        store.execute_read.side_effect = [
            [
                {
                    "id": str(entity_id),
                    "merge_key": "Person:bob",
                    "name": "Bob",
                },
                {"n": {"id": "bad", "labels": ["Person"], "properties": {}}},
            ]
        ]
        result = await exact_match_lookup([m], graph_store=store)
        assert result[0].id == entity_id
        assert set(result) == {0}

    async def test_handles_no_rows(self) -> None:
        """No rows yields empty map entry."""
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="NoHit", char_start=0, char_end=5
        )
        store.execute_read.side_effect = [[]]
        result = await exact_match_lookup([m], graph_store=store)
        assert result == {}

    async def test_reingest_of_absorbed_name_resolves_to_survivor(self) -> None:
        """A name absorbed into a survivor still resolves there on re-ingest.

        Regression test: tombstone_query clears merge_key on absorption, so
        a later mention of the absorbed name can only be found through the
        merge-key alias table (fetch_by_merge_keys_query,
        upsert_merge_alias_query). Without that alias, this mention would
        find nothing and a duplicate "Bob" entity would be created instead
        of resolving to the existing survivor.
        """
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read.side_effect = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(tombstone_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Bob",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                            "merged_into": str(survivor_id),
                        },
                    },
                }
            ],
            [
                {
                    "n": {
                        "id": str(survivor_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Robert",
                            "merge_key": "Person:robert",
                            "merged_from": [str(tombstone_id)],
                            "merge_count": 2,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ],
        ]
        result = await exact_match_lookup([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_reingest_resolves_with_driver_shaped_tombstone_row(
        self,
    ) -> None:
        """Reingest still resolves when the tombstone row has no labels key.

        Regression test: a real Neo4j driver's RETURN n never carries a
        labels key -- only _tombstone_row's mock form did, masking a bug
        where the tombstone's own node was parsed into an Entity (to learn
        its label) before its merged_into chain was ever checked. With
        merge_key already stripped by clear_tombstone_merge_keys_query, a
        driver-shaped tombstone row has neither a labels list nor a
        merge_key to derive a label from, so that parse always failed and
        the mention was silently dropped instead of resolving to the
        survivor.
        """
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read.side_effect = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(tombstone_id),
                        "name": "Bob",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "merged_into": str(survivor_id),
                    },
                }
            ],
            [
                {
                    "n": {
                        "id": str(survivor_id),
                        "name": "Robert",
                        "merge_key": "Person:robert",
                        "merged_from": [str(tombstone_id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                    }
                }
            ],
        ]
        result = await exact_match_lookup([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_accepted_alias_with_different_name_resolves_to_entity(
        self,
    ) -> None:
        """A mention resolves via an alias even when it never was the name.

        Regression test: when resolution joins "Bob" and "Robert" into one
        survivor named "Robert", an alias for "Person:bob" is written
        pointing at that entity even though the entity's own name was never
        "Bob". Mapping the returned row back to the "Bob" mention must use
        the merge_key the row's alias was queried on, not one re-derived
        from the entity's current name -- re-deriving would compute
        "Person:robert" and silently fail to map "Bob" at all.
        """
        store = AsyncMock()
        cid = uuid4()
        mention = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        entity_id = uuid4()
        store.execute_read.side_effect = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(entity_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Robert",
                            "merge_key": "Person:robert",
                            "merged_from": [],
                            "merge_count": 2,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    },
                }
            ]
        ]
        result = await exact_match_lookup([mention], graph_store=store)
        assert result[0].id == entity_id
        assert result[0].name == "Robert"

    async def test_transient_chain_read_failure_propagates(self) -> None:
        """A transient error resolving a tombstone chain must not be missed.

        Regression test: _resolve_tombstone_chain used to catch every
        exception from its chain-follow read and return whatever survivor it
        had so far (None on the first hop). _global_exact_match then treated
        that as "no match" and the caller would create a duplicate entity for
        an already-known name instead of surfacing the failure.
        """
        store = AsyncMock()
        tombstone_id = uuid4()
        survivor_id = uuid4()
        mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Bob", char_start=0, char_end=3
        )
        first_response = [
            {
                "merge_key": "Person:bob",
                "n": {
                    "id": str(tombstone_id),
                    "labels": ["Person"],
                    "properties": {
                        "name": "Bob",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "merged_into": str(survivor_id),
                    },
                },
            }
        ]
        store.execute_read.side_effect = [
            first_response,
            ConnectionError("simulated transient DB error"),
        ]
        with pytest.raises(ConnectionError, match="simulated transient DB error"):
            await exact_match_lookup([mention], graph_store=store)


class TestBuildRelationNeighbors:
    """build_relation_neighbors renders each direction of every relation."""

    def test_contributes_both_directions(self) -> None:
        """Both endpoints name the other, with the relation label."""
        entities = [_mention("Ada", "Person"), _mention("Acme", "Org")]

        neighbors = build_relation_neighbors(entities, [_relation(0, 1)])

        assert neighbors == {0: ["WORKS_AT Acme"], 1: ["WORKS_AT Ada"]}

    def test_caps_each_index_at_max_neighbors(self) -> None:
        """An index with more relations than the cap keeps only the cap."""
        entities = [_mention("Ada")] + [_mention(f"Other {i}") for i in range(7)]
        relations = [_relation(0, target) for target in range(1, 8)]

        neighbors = build_relation_neighbors(entities, relations)

        assert len(neighbors[0]) == MAX_NEIGHBORS_PER_ENTITY
        assert neighbors[0] == [
            "WORKS_AT Other 0",
            "WORKS_AT Other 1",
            "WORKS_AT Other 2",
            "WORKS_AT Other 3",
            "WORKS_AT Other 4",
        ]

    def test_entity_with_no_relations_has_no_key(self) -> None:
        """An index no relation names is absent, not present and empty."""
        entities = [_mention("Ada"), _mention("Acme"), _mention("Grace")]

        neighbors = build_relation_neighbors(entities, [_relation(0, 1)])

        assert 2 not in neighbors

    def test_empty_relations_returns_empty_map(self) -> None:
        """No relation mentions means no neighbor context at all."""
        assert build_relation_neighbors([_mention("Ada")], []) == {}


class TestFetchPersistedNeighbors:
    """fetch_persisted_neighbors batches one read for every requested id."""

    async def test_batches_all_ids_into_one_read(self) -> None:
        """Every id goes into one query, and rows become neighbor strings."""
        first, second = uuid4(), uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {"entity_id": str(first), "rel_type": "WORKS_AT", "neighbor_name": "Acme"},
            {"entity_id": str(second), "rel_type": "KNOWS", "neighbor_name": "Ada"},
        ]

        neighbors = await fetch_persisted_neighbors(
            [first, second],
            graph_store=graph_store,
            exclude_relation_types=["MATCHES"],
        )

        graph_store.execute_read.assert_awaited_once()
        _, params = graph_store.execute_read.await_args.args
        assert params["ids"] == [str(first), str(second)]
        assert params["exclude_types"] == ["MATCHES"]
        assert neighbors == {first: ["WORKS_AT Acme"], second: ["KNOWS Ada"]}

    async def test_skips_malformed_rows(self) -> None:
        """A row missing keys or carrying a bad uuid is skipped, not raised."""
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {"entity_id": str(entity_id), "rel_type": "WORKS_AT"},
            {"entity_id": "not-a-uuid", "rel_type": "KNOWS", "neighbor_name": "Ada"},
            {"entity_id": str(entity_id), "rel_type": "KNOWS", "neighbor_name": "Ada"},
        ]

        neighbors = await fetch_persisted_neighbors(
            [entity_id],
            graph_store=graph_store,
            exclude_relation_types=[],
        )

        assert neighbors == {entity_id: ["KNOWS Ada"]}

    async def test_caps_repeated_rows_for_the_same_entity(self) -> None:
        """Duplicate requested ids do not let returned rows exceed the cap."""
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "entity_id": str(entity_id),
                "rel_type": "KNOWS",
                "neighbor_name": f"Person {index}",
            }
            for index in range(MAX_NEIGHBORS_PER_ENTITY + 2)
        ]

        neighbors = await fetch_persisted_neighbors(
            [entity_id, entity_id],
            graph_store=graph_store,
            exclude_relation_types=[],
        )

        assert neighbors[entity_id] == [
            f"KNOWS Person {index}" for index in range(MAX_NEIGHBORS_PER_ENTITY)
        ]

    async def test_empty_ids_skips_the_read(self) -> None:
        """No ids means no query at all."""
        graph_store = AsyncMock()

        neighbors = await fetch_persisted_neighbors(
            [], graph_store=graph_store, exclude_relation_types=["MATCHES"]
        )

        assert neighbors == {}
        graph_store.execute_read.assert_not_awaited()
